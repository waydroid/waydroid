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
from gi.repository import GLib, Gio

stopping = False

def transition_desktop_files(apps_dir, andromeda_data):
    if not os.path.exists(apps_dir):
        return

    desktop_files = [f for f in os.listdir(apps_dir) if f.startswith("waydroid.") and f.endswith(".desktop")]
    for old_file in desktop_files:
        package_name = old_file.replace("waydroid.", "").replace(".desktop", "")
        new_file = f"android.{package_name}.desktop"
        old_path = os.path.join(apps_dir, old_file)
        new_path = os.path.join(apps_dir, new_file)

        try:
            with open(old_path, 'r') as f:
                content = f.read()

            content = content.replace("Exec=waydroid app launch", "Exec=andromeda app launch")
            content = content.replace("Exec=waydroid app intent", "Exec=andromeda app intent")
            content = content.replace("X-WayDroid-App", "X-Andromeda-App")
            content = content.replace("Categories=X-Waydroid-App", "Categories=X-Andromeda-App")


            content = content.replace("/home/furios/.local/share/waydroid/data/icons/",
                                      "/home/furios/.local/share/andromeda/data/icons/")
            content = content.replace("Icon=/var/lib/waydroid/data/icons/",
                                     "Icon=/var/lib/andromeda/data/icons/")
            content = content.replace("/waydroid/", "/andromeda/")

            with open(new_path, 'w') as f:
                f.write(content)

            os.remove(old_path)
            logging.info(f"Migrated desktop file: {old_file} to {new_file}")
        except Exception as e:
            logging.error(f"Failed to migrate desktop file {old_file}: {e}")

    try:
        schema = Gio.Settings.new("sm.puri.phosh")
        if schema.list_keys() and "favorites" in schema.list_keys():
            favorites = schema.get_strv("favorites")
            updated = False
            new_favorites = []

            for item in favorites:
                if item.startswith("waydroid."):
                    new_item = item.replace("waydroid.", "android.")
                    new_favorites.append(new_item)
                    updated = True
                    logging.info(f"Updating favorite: {item} to {new_item}")
                else:
                    new_favorites.append(item)

            if updated:
                schema.set_strv("favorites", new_favorites)
                logging.info("Updated phosh favorites")
    except Exception:
        pass

def makeDesktopFile(appInfo, andromeda_data, apps_dir):
    if appInfo is None:
        return -1

    showApp = False
    for cat in appInfo["categories"]:
        if cat.strip() == "android.intent.category.LAUNCHER" or cat.strip() == "android.intent.category.INFO":
            showApp = True
    if not showApp:
        return -1

    packageName = appInfo["packageName"]

    HIDDEN_PACKAGES = [
        "com.android.documentsui",
        "com.android.inputmethod.latin",
        "com.android.settings",
        "com.google.android.gms",
        "com.android.vending",
        "org.lineageos.jelly",
        "org.lineageos.aperture",
        "com.android.messaging",
        "com.android.dialer",
        "io.furios.launcher"
    ]

    hide = packageName in HIDDEN_PACKAGES

    desktop_file_path = apps_dir + "/android." + packageName + ".desktop"
    if not os.path.exists(desktop_file_path):
        with open(desktop_file_path, "w") as desktop_file:
            desktop_file.write(f"""\
[Desktop Entry]
Type=Application
Name={appInfo["name"]}
Exec=andromeda app launch {packageName}
Icon={andromeda_data}/icons/{packageName}.png
Categories=X-Andromeda-App;
X-Purism-FormFactor=Workstation;Mobile;
Actions=app_settings;
NoDisplay={str(hide).lower()}

[Desktop Action app_settings]
Name=App Settings
Exec=andromeda app intent android.settings.APPLICATION_DETAILS_SETTINGS package:{packageName}
Icon={andromeda_data}/icons/com.android.settings.png
""")
        return 0

def start(args, session, unlocked_cb=None):
    andromeda_data = session["andromeda_data"]
    apps_dir = session["xdg_data_home"] + "/applications/"

    def userUnlocked(uid):
        cfg = tools.config.load(args)
        logging.info("Android with user {} is ready".format(uid))

        if cfg["andromeda"]["auto_adb"] == "True":
            tools.helpers.net.adb_connect(args)

        transition_desktop_files(apps_dir, andromeda_data)

        platformService = IPlatform.get_service(args)
        if platformService:
            if not os.path.exists(apps_dir):
                os.mkdir(apps_dir, 0o700)
            appsList = platformService.getAppsInfo()
            for app in appsList:
                makeDesktopFile(app, andromeda_data, apps_dir)
            multiwin = platformService.getprop("persist.andromeda.multi_windows", "false")
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
            desktop_file_path = apps_dir + "/android." + packageName + ".desktop"
            if mode == 0:
                # Package added
                makeDesktopFile(appInfo, andromeda_data, apps_dir)
            elif mode == 1:
                if os.path.isfile(desktop_file_path):
                    os.remove(desktop_file_path)
            else:
                if os.path.isfile(desktop_file_path):
                    if makeDesktopFile(appInfo, andromeda_data, apps_dir) == -1:
                        os.remove(desktop_file_path)

    def setup_dbus_signals():
        bus = dbus.SystemBus()
        bus.add_signal_receiver(
            userUnlocked,
            signal_name='userUnlocked',
            dbus_interface='io.furios.Andromeda.StateChange',
            bus_name='io.furios.Andromeda.StateChange'
        )
        bus.add_signal_receiver(
            packageStateChanged,
            signal_name='packageStateChanged',
            dbus_interface='io.furios.Andromeda.StateChange',
            bus_name='io.furios.Andromeda.StateChange'
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
