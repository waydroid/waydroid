# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import shutil
import time
import tools.config
import tools.helpers.props
from tools.interfaces import IPlatform
from tools.interfaces import IStatusBarService

def install(args):
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        if session_cfg["session"]["state"] == "RUNNING":
            tmp_dir = session_cfg["session"]["waydroid_data"] + "/waydroid_tmp"
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            shutil.copyfile(args.PACKAGE, tmp_dir + "/base.apk")
            platformService = IPlatform.get_service(args)
            if platformService:
                platformService.installApp("/data/waydroid_tmp/base.apk")
            shutil.rmtree(tmp_dir)
        else:
            logging.error("WayDroid container is {}".format(
                session_cfg["session"]["state"]))
    else:
        logging.error("WayDroid session is stopped")

def remove(args):
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        if session_cfg["session"]["state"] == "RUNNING":
            platformService = IPlatform.get_service(args)
            if platformService:
                ret = platformService.removeApp(args.PACKAGE)
                if ret != 0:
                    logging.error("Failed to uninstall package: {}".format(args.PACKAGE))
            else:
                logging.error("Failed to access IPlatform service")
        else:
            logging.error("WayDroid container is {}".format(
                session_cfg["session"]["state"]))
    else:
        logging.error("WayDroid session is stopped")

def maybeLaunchLater(args, retry, launchNow):
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()

        if session_cfg["session"]["state"] == "RUNNING":
            launchNow()
        elif session_cfg["session"]["state"] == "FROZEN" or session_cfg["session"]["state"] == "UNFREEZE":
            session_cfg["session"]["state"] = "UNFREEZE"
            tools.config.save_session(session_cfg)
            while session_cfg["session"]["state"] != "RUNNING":
                session_cfg = tools.config.load_session()
            launchNow()
        else:
            logging.error("WayDroid container is {}".format(
                session_cfg["session"]["state"]))
    else:
        logging.error("Starting waydroid session")
        tools.actions.session_manager.start(args, retry)

def launch(args):
    def justLaunch():
        platformService = IPlatform.get_service(args)
        if platformService:
            platformService.setprop("waydroid.active_apps", args.PACKAGE)
            ret = platformService.launchApp(args.PACKAGE)
            multiwin = platformService.getprop(
                "persist.waydroid.multi_windows", "false")
            if multiwin == "false":
                platformService.settingsPutString(
                    2, "policy_control", "immersive.status=*")
            else:
                platformService.settingsPutString(
                    2, "policy_control", "immersive.full=*")
        else:
            logging.error("Failed to access IPlatform service")
    maybeLaunchLater(args, launch, justLaunch)

def list(args):
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        if session_cfg["session"]["state"] == "RUNNING":
            platformService = IPlatform.get_service(args)
            if platformService:
                appsList = platformService.getAppsInfo()
                for app in appsList:
                    print("Name: " + app["name"])
                    print("packageName: " + app["packageName"])
                    print("categories:")
                    for cat in app["categories"]:
                        print("\t" + cat)
            else:
                logging.error("Failed to access IPlatform service")
        else:
            logging.error("WayDroid container is {}".format(
                session_cfg["session"]["state"]))
    else:
        logging.error("WayDroid session is stopped")

def showFullUI(args):
    def justShow():
        platformService = IPlatform.get_service(args)
        if platformService:
            platformService.setprop("waydroid.active_apps", "Waydroid")
            platformService.settingsPutString(2, "policy_control", "null*")
            # HACK: Refresh display contents
            statusBarService = IStatusBarService.get_service(args)
            if statusBarService:
                statusBarService.expand()
                time.sleep(0.5)
                statusBarService.collapse()
    maybeLaunchLater(args, showFullUI, justShow)

def intent(args):
    def justLaunch():
        platformService = IPlatform.get_service(args)
        if platformService:
            ret = platformService.launchIntent(args.ACTION, args.URI)
            if ret == "":
                return
            pkg = ret if ret != "android" else "Waydroid"
            platformService.setprop("waydroid.active_apps", pkg)
            multiwin = platformService.getprop(
                "persist.waydroid.multi_windows", "false")
            if multiwin == "false":
                platformService.settingsPutString(
                    2, "policy_control", "immersive.status=*")
            else:
                platformService.settingsPutString(
                    2, "policy_control", "immersive.full=*")
        else:
            logging.error("Failed to access IPlatform service")
    maybeLaunchLater(args, intent, justLaunch)
