# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import glob
import logging
import os
import threading
import tools.config
import tools.helpers.net
from tools.interfaces import IUserMonitor
from tools.interfaces import IPlatform
from gi.repository import GLib

stopping = False

def start(args, session, unlocked_cb=None):
    waydroid_data = session["waydroid_data"]
    apps_dir = session["xdg_data_home"] + "/applications/"

    system_apps = [
        "com.android.calculator2",
        "com.android.camera2",
        "com.android.contacts",
        "com.android.deskclock",
        "com.android.documentsui",
        "com.android.email",
        "com.android.gallery3d",
        "com.android.inputmethod.latin",
        "com.android.settings",
        "com.google.android.gms",
        "org.lineageos.aperture",
        "org.lineageos.eleven",
        "org.lineageos.etar",
        "org.lineageos.jelly",
        "org.lineageos.recorder"
    ]


    def prepend_list(old_list, new_list):
        for s in reversed(new_list):
            if s not in old_list:
                old_list.insert(0, s)

    def glib_key_file_get_string_list(key_file, group, key):
        try:
            return key_file.get_string_list(group, key)
        except:
            return []

    def glib_key_file_prepend_string_list(key_file, group, key, new_list):
        old_list = glib_key_file_get_string_list(key_file, group, key)
        prepend_list(old_list, new_list)
        key_file.set_string_list(group, key, new_list)

    def glib_key_file_has_value(key_file, group, key):
        try:
            key_file.get_value(group, key)
            return True
        except:
            return False


    # Creates, deletes, or updates desktop file
    def updateDesktopFile(appInfo):
        if appInfo is None:
            return

        showApp = False
        for cat in appInfo["categories"]:
            if cat.strip() == "android.intent.category.LAUNCHER":
                showApp = True
        if not showApp:
            try:
                os.remove(desktop_file_path)
            except:
                pass

        packageName = appInfo["packageName"]

        desktop_file_path = apps_dir + "/waydroid." + packageName + ".desktop"
        desktop_file = GLib.KeyFile()
        try:
            flags = GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS
            desktop_file.load_from_file(desktop_file_path, flags)
        except:
            pass

        desktop_file.set_string("Desktop Entry", "Type", "Application")
        desktop_file.set_string("Desktop Entry", "Name", appInfo["name"])
        desktop_file.set_string("Desktop Entry", "Exec", f"waydroid app launch {packageName}")
        desktop_file.set_string("Desktop Entry", "Icon", f"{waydroid_data}/icons/{packageName}.png")
        glib_key_file_prepend_string_list(desktop_file, "Desktop Entry", "Categories", ["X-WayDroid-App"])
        desktop_file.set_string_list("Desktop Entry", "X-Purism-FormFactor", ["Workstation", "Mobile"])
        glib_key_file_prepend_string_list(desktop_file, "Desktop Entry", "Actions", ["app_settings"])
        if packageName in system_apps and not glib_key_file_has_value(desktop_file, "Desktop Entry", "NoDisplay"):
            desktop_file.set_boolean("Desktop Entry", "NoDisplay", True)

        desktop_file.set_string("Desktop Action app_settings", "Name", "App Settings")
        desktop_file.set_string("Desktop Action app_settings", "Exec", f"waydroid app intent android.settings.APPLICATION_DETAILS_SETTINGS package:{packageName}")
        desktop_file.set_string("Desktop Action app_settings", "Icon", f"{waydroid_data}/icons/com.android.settings.png")

        desktop_file.save_to_file(desktop_file_path)


    def updateWaydroidDesktopFile(hide):
        desktop_file_path = apps_dir + "/Waydroid.desktop"
        # If the user has set the desktop file as read-only, we won't replace it
        if os.path.isfile(desktop_file_path) and not os.access(desktop_file_path, os.W_OK):
            logging.info(f"Desktop file '{desktop_file_path}' is not writeable, not updating it")
            return

        desktop_file = GLib.KeyFile()
        try:
            flags = GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS
            desktop_file.load_from_file(desktop_file_path, flags)
        except:
            pass

        desktop_file.set_string("Desktop Entry", "Type", "Application")
        desktop_file.set_string("Desktop Entry", "Name", "Waydroid")
        desktop_file.set_string("Desktop Entry", "Exec", "waydroid show-full-ui")
        glib_key_file_prepend_string_list(desktop_file, "Desktop Entry", "Categories", ["X-WayDroid-App", "Utility"])
        desktop_file.set_string_list("Desktop Entry", "X-Purism-FormFactor", ["Workstation", "Mobile"])
        desktop_file.set_string("Desktop Entry", "Icon", "waydroid")
        desktop_file.set_boolean("Desktop Entry", "NoDisplay", hide)

        desktop_file.save_to_file(desktop_file_path)

    def userUnlocked(uid):
        cfg = tools.config.load(args)
        logging.info("Android with user {} is ready".format(uid))

        if cfg["waydroid"]["auto_adb"] == "True":
            try:
                tools.helpers.net.adb_connect(args)
            except:
                pass

        platformService = IPlatform.get_service(args)
        if platformService:
            if not os.path.exists(apps_dir):
                os.mkdir(apps_dir, 0o700)
            appsList = platformService.getAppsInfo()
            for app in appsList:
                updateDesktopFile(app)
            for existing in glob.iglob(f'{apps_dir}/waydroid.*.desktop'):
                if os.path.basename(existing) not in map(lambda appInfo: f"waydroid.{appInfo['packageName']}.desktop", appsList):
                    os.remove(existing)
            multiwin = platformService.getprop("persist.waydroid.multi_windows", "false")
            updateWaydroidDesktopFile(multiwin == "true")
        if unlocked_cb:
            unlocked_cb()

    def packageStateChanged(mode, packageName, uid):
        platformService = IPlatform.get_service(args)
        if platformService:
            desktop_file_path = apps_dir + "/waydroid." + packageName + ".desktop"
            if mode == IUserMonitor.PACKAGE_REMOVED:
                try:
                    os.remove(desktop_file_path)
                except:
                    pass
            else:
                appInfo = platformService.getAppInfo(packageName)
                updateDesktopFile(appInfo)

    def service_thread():
        while not stopping:
            IUserMonitor.add_service(args, userUnlocked, packageStateChanged)

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
