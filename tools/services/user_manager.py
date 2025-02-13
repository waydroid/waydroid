# Copyright 2021 Erfan Abdi
# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import dbus
import threading
import tools.config
import tools.helpers.net
from tools.helpers import ipc, drivers
from tools.interfaces import IUserMonitor
from tools.interfaces import IPlatform
import dbus.mainloop.glib
from gi.repository import GLib

stopping = False

def start(args, session, unlocked_cb=None):
    waydroid_data = session["waydroid_data"]
    apps_dir = session["xdg_data_home"] + "/applications/"

    def makeDesktopFile(appInfo):
        if appInfo is None:
            return -1

        showApp = False
        for cat in appInfo["categories"]:
            if cat.strip() == "android.intent.category.LAUNCHER":
                showApp = True
        if not showApp:
            return -1

        packageName = appInfo["packageName"]

        HIDDEN_PACKAGES = [
            "com.android.documentsui",
            "com.android.inputmethod.latin",
            "com.android.settings",
            "com.google.android.gms",
            "org.lineageos.jelly",
            "org.lineageos.aperture",
            "com.android.messaging",
            "com.android.dialer",
            "io.furios.launcher"
        ]

        hide = packageName in HIDDEN_PACKAGES

        desktop_file_path = apps_dir + "/waydroid." + packageName + ".desktop"
        if not os.path.exists(desktop_file_path):
            with open(desktop_file_path, "w") as desktop_file:
                desktop_file.write(f"""\
[Desktop Entry]
Type=Application
Name={appInfo["name"]}
Exec=waydroid app launch {packageName}
Icon={waydroid_data}/icons/{packageName}.png
Categories=X-WayDroid-App;
X-Purism-FormFactor=Workstation;Mobile;
Actions=app_settings;
NoDisplay={str(hide).lower()}

[Desktop Action app_settings]
Name=App Settings
Exec=waydroid app intent android.settings.APPLICATION_DETAILS_SETTINGS package:{packageName}
Icon={waydroid_data}/icons/com.android.settings.png
""")
            return 0

    def userUnlocked(uid):
        cfg = tools.config.load(args)
        logging.info("Android with user {} is ready".format(uid))

        if cfg["waydroid"]["auto_adb"] == "True":
            tools.helpers.net.adb_connect(args)

        platformService = IPlatform.get_service(args)
        if platformService:
            if not os.path.exists(apps_dir):
                os.mkdir(apps_dir, 0o700)
            appsList = platformService.getAppsInfo()
            for app in appsList:
                makeDesktopFile(app)
            multiwin = platformService.getprop("persist.waydroid.multi_windows", "false")
        if unlocked_cb:
            unlocked_cb()

        cm = ipc.DBusContainerService()
        cm.ForceFinishSetup()

        timezone = get_timezone()
        if timezone:
            cm.Setprop("persist.sys.timezone", timezone)

    def packageStateChanged(mode, packageName, uid):
        platformService = IPlatform.get_service(args)
        if platformService:
            appInfo = platformService.getAppInfo(packageName)
            desktop_file_path = apps_dir + "/waydroid." + packageName + ".desktop"
            if mode == 0:
                # Package added
                makeDesktopFile(appInfo)
            elif mode == 1:
                if os.path.isfile(desktop_file_path):
                    os.remove(desktop_file_path)
            else:
                if os.path.isfile(desktop_file_path):
                    if makeDesktopFile(appInfo) == -1:
                        os.remove(desktop_file_path)

    def setup_dbus_signals():
        bus = dbus.SystemBus()
        bus.add_signal_receiver(
            userUnlocked,
            signal_name='userUnlocked',
            dbus_interface='id.waydro.StateChange',
            bus_name='id.waydro.StateChange'
        )
        bus.add_signal_receiver(
            packageStateChanged,
            signal_name='packageStateChanged',
            dbus_interface='id.waydro.StateChange',
            bus_name='id.waydro.StateChange'
        )

    def service_thread_gbinder():
        while not stopping:
            IUserMonitor.add_service(args, userUnlocked, packageStateChanged)

    def service_thread_statechange():
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        setup_dbus_signals()

        args.userMonitorLoop = GLib.MainLoop()
        while not stopping:
            try:
                args.userMonitorLoop.run()
            except Exception as e:
                logging.error(f"Error in user monitor loop: {e}")
                if not stopping:
                    continue
                break

    def service_thread():
        if drivers.should_use_statechange():
            service_thread_statechange()
        else:
            service_thread_gbinder()

    global stopping
    stopping = False
    args.user_manager = threading.Thread(target=service_thread)
    args.user_manager.start()

def stop(args):
    global stopping
    stopping = True
    try:
        if args.userMonitorLoop:
            args.userMonitorLoop.quit()
    except AttributeError:
        logging.debug("UserMonitor service is not even started")

def get_timezone():
    localtime_path = '/etc/localtime'

    try:
        if os.path.exists(localtime_path):
            if os.path.islink(localtime_path):
                target = os.readlink(localtime_path)
                timezone = '/'.join(target.split('/')[-2:])
                return timezone
    except Exception as e:
        logging.error(f"Failed to get timezone: {e}")
    return False
