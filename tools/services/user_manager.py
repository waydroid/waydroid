# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import threading
import tools.config
import tools.helpers.net
from tools.interfaces import IUserMonitor
from tools.interfaces import IPlatform

stopping = False

def start(args, session, unlocked_cb=None):
    waydroid_data = session["waydroid_data"]
    apps_dir = session["xdg_data_home"] + "/applications/"

    def makeMenuFiles():
        home_directory = os.environ['HOME']
        config_menus_dir = f'{home_directory}/.config/menus/applications-merged'
        local_share_desktop_directories_dir = f'{home_directory}/.local/share/desktop-directories'
        if not os.path.exists(config_menus_dir):
            os.makedirs(config_menus_dir)
        if not os.path.exists(local_share_desktop_directories_dir):
            os.makedirs(local_share_desktop_directories_dir)

        if not os.path.isfile(f'{config_menus_dir}/waydroid.menu'):
            with open(f'{config_menus_dir}/waydroid.menu', 'w') as f:
                lines = ['<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"\n']
                lines.append('"http://www.freedesktop.org/standards/menu-spec/menu-1.0.dtd">\n')
                lines.append('<Menu>\n')
                lines.append('\t<Name>Applications</Name>\n')
                lines.append('\t<Menu>\n')
                lines.append('\t\t<Name>Waydroid</Name>\n')
                lines.append('\t\t<Directory>waydroid.directory</Directory>\n')
                lines.append('\t\t<Include>\n')
                lines.append('\t\t\t<Category>X-WayDroid-App</Category>\n')
                lines.append('\t\t</Include>\n')
                lines.append('\t</Menu>\n')
                lines.append('</Menu>\n')
                lines.append('</Menu>\n')
                f.writelines(lines)

        if not os.path.isfile(f'{local_share_desktop_directories_dir}/waydroid.directory'):
            with open(f'{local_share_desktop_directories_dir}/waydroid.directory', 'w') as g:
                lines = ['[Desktop Entry]\n']
                lines.append('Name=Waydroid\n')
                lines.append('Icon=waydroid\n')
                lines.append('Type=Directory\n')
                g.writelines(lines)

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

        desktop_file_path = apps_dir + "/waydroid." + packageName + ".desktop"
        if not os.path.exists(desktop_file_path):
            lines = ["[Desktop Entry]", "Type=Application"]
            lines.append("Name=" + appInfo["name"])
            lines.append("Exec=waydroid app launch " + packageName)
            lines.append("Icon=" + waydroid_data + "/icons/" + packageName + ".png")
            lines.append("Categories=X-WayDroid-App;")
            lines.append("X-Purism-FormFactor=Workstation;Mobile;")
            lines.append("Actions=app_settings;")
            lines.append("[Desktop Action app_settings]")
            lines.append("Name=App Settings")
            lines.append("Exec=waydroid app intent android.settings.APPLICATION_DETAILS_SETTINGS package:" + packageName)
            desktop_file = open(desktop_file_path, "w")
            for line in lines:
                desktop_file.write(line + "\n")
            desktop_file.close()
            os.chmod(desktop_file_path, 0o644)
            return 0

    def makeWaydroidDesktopFile(hide):
        desktop_file_path = apps_dir + "/Waydroid.desktop"
        if os.path.isfile(desktop_file_path):
            os.remove(desktop_file_path)
        lines = ["[Desktop Entry]", "Type=Application"]
        lines.append("Name=Waydroid")
        lines.append("Exec=waydroid show-full-ui")
        lines.append("Categories=X-WayDroid-App;")
        lines.append("X-Purism-FormFactor=Workstation;Mobile;")
        if hide:
            lines.append("NoDisplay=true")
        lines.append("Icon=waydroid")
        desktop_file = open(desktop_file_path, "w")
        for line in lines:
            desktop_file.write(line + "\n")
        desktop_file.close()
        os.chmod(desktop_file_path, 0o644)

    def userUnlocked(uid):
        logging.info("Android with user {} is ready".format(uid))

        tools.helpers.net.adb_connect(args)

        platformService = IPlatform.get_service(args)
        if platformService:
            if not os.path.exists(apps_dir):
                os.mkdir(apps_dir)
                os.chmod(apps_dir, 0o700)
            appsList = platformService.getAppsInfo()
            for app in appsList:
                makeDesktopFile(app)
            multiwin = platformService.getprop("persist.waydroid.multi_windows", "false")
            if multiwin == "false":
                makeWaydroidDesktopFile(False)
            else:
                makeWaydroidDesktopFile(True)
        if unlocked_cb:
            unlocked_cb()

    def packageStateChanged(mode, packageName, uid):
        platformService = IPlatform.get_service(args)
        if platformService:
            appInfo = platformService.getAppInfo(packageName)
            desktop_file_path = apps_dir + "/waydroid." + packageName + ".desktop"
            makeMenuFiles()
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
