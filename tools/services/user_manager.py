# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import glob
import logging
import os
import threading
import tools.config
import tools.helpers.net
from pathlib import Path
from contextlib import suppress
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
        except GLib.GError:
            return []

    def glib_key_file_prepend_string_list(key_file, group, key, new_list):
        lst = glib_key_file_get_string_list(key_file, group, key)
        prepend_list(lst, new_list)
        key_file.set_string_list(group, key, lst)

    def glib_key_file_has_value(key_file, group, key):
        try:
            key_file.get_value(group, key)
            return True
        except GLib.GError:
            return False

    # Migrate waydroid user configs after upgrade
    def user_migration():
        apps_dir = session["xdg_data_home"] + "/applications/"
        state_dir = session["waydroid_user_state"]
        if not any(glob.iglob(f'{apps_dir}/waydroid.*.desktop')):
            # first ever run, no need to migrate
            return

        if not os.path.exists(os.path.join(state_dir, ".migrated-main-desktop-file")):
            Path(os.path.join(apps_dir, "Waydroid.desktop")).unlink(missing_ok=True)
            Path(os.path.join(state_dir, ".migrated-main-desktop-file")).touch()

        if not os.path.exists(os.path.join(state_dir, ".migrated-app-settings-desktop-action")):
            for app in glob.iglob(f'{apps_dir}/waydroid.*.desktop'):
                with suppress(GLib.GError):
                    desktop_file = GLib.KeyFile()
                    flags = GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS
                    desktop_file.load_from_file(app, flags)
                    with suppress(GLib.GError):
                        desktop_file.remove_group("Desktop Action app_settings")
                    with suppress(GLib.GError, ValueError):
                        actions = glib_key_file_get_string_list(desktop_file, "Desktop Entry", "Actions")
                        actions.remove("app_settings")
                        desktop_file.set_string_list("Desktop Entry", "Actions", actions)
                    desktop_file.save_to_file(app)
            Path(os.path.join(state_dir, ".migrated-app-settings-desktop-action")).touch()

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
        with suppress(GLib.GError):
            flags = GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS
            desktop_file.load_from_file(desktop_file_path, flags)

        desktop_file.set_string("Desktop Entry", "Type", "Application")
        desktop_file.set_string("Desktop Entry", "Name", appInfo["name"])
        desktop_file.set_string("Desktop Entry", "Exec", f"waydroid app launch {packageName}")
        desktop_file.set_string("Desktop Entry", "Icon", f"{waydroid_data}/icons/{packageName}.png")
        glib_key_file_prepend_string_list(desktop_file, "Desktop Entry", "Categories", ["X-WayDroid-App"])
        desktop_file.set_string_list("Desktop Entry", "X-Purism-FormFactor", ["Workstation", "Mobile"])
        glib_key_file_prepend_string_list(desktop_file, "Desktop Entry", "Actions", ["app-settings"])
        if packageName in system_apps and not glib_key_file_has_value(desktop_file, "Desktop Entry", "NoDisplay"):
            desktop_file.set_boolean("Desktop Entry", "NoDisplay", True)

        desktop_file.set_string("Desktop Action app-settings", "Name", "App Settings")
        desktop_file.set_string("Desktop Action app-settings", "Exec", f"waydroid app intent android.settings.APPLICATION_DETAILS_SETTINGS package:{packageName}")
        desktop_file.set_string("Desktop Action app-settings", "Icon", f"{waydroid_data}/icons/com.android.settings.png")

        desktop_file.save_to_file(desktop_file_path)


    def userUnlocked(uid):
        cfg = tools.config.load(args)
        logging.info("Android with user {} is ready".format(uid))

        user_migration()

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
