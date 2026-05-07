# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading
import time
import os
import tools.actions.container_manager
import tools.actions.session_manager
import tools.config
from tools import helpers
from tools.interfaces import IHardware

stopping = False

def start(args):
    def enableNFC(enable):
        logging.debug("Function enableNFC not implemented")

    def enableBluetooth(enable):
        logging.debug("Function enableBluetooth not implemented")

    def suspend():
        cfg = tools.config.load(args)
        if cfg["waydroid"]["suspend_action"] == "stop":
            tools.actions.session_manager.stop(args)
        else:
            tools.actions.container_manager.freeze(args)

    def reboot():
        helpers.lxc.stop(args)
        helpers.lxc.start(args)

    def upgrade(system_zip, system_time, vendor_zip, vendor_time):
        helpers.lxc.stop(args)
        helpers.images.umount_rootfs(args)
        helpers.images.replace(args, system_zip, system_time,
                               vendor_zip, vendor_time)
        args.session["background_start"] = "false"
        helpers.images.mount_rootfs(args, args.images_path, args.session)
        helpers.protocol.set_aidl_version(args)
        helpers.lxc.start(args)

    def shutdownRequest(reason, in_thread = False):
        if not in_thread:
            threading.Thread(target=shutdownRequest, args=(reason, True)).start()
            return

        is_reboot = reason and reason.startswith("1")
        tries = 0

        while helpers.lxc.status(args) != "STOPPED":
            if tries >= 30:
                logging.debug(f"Android is still not stopped, give up waiting after {tries} seconds")
                return

            logging.debug("Waiting for Android to shutdown")
            time.sleep(1)
            tries += 1

        if is_reboot:
            helpers.lxc.start(args)
        else:
            tools.actions.session_manager.stop(args)

    def service_thread():
        while not stopping:
            IHardware.add_service(
                args, enableNFC, enableBluetooth, suspend, reboot, upgrade, shutdownRequest)

    global stopping
    stopping = False
    args.hardware_manager = threading.Thread(target=service_thread)
    args.hardware_manager.start()

def stop(args):
    global stopping
    stopping = True
    try:
        if args.hardwareLoop:
            args.hardwareLoop.quit()
    except AttributeError:
        logging.debug("Hardware service is not even started")
