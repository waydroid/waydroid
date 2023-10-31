# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading
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
        if os.path.exists(system_zip):
            if not helpers.images.validate(args, "system_ota", system_zip):
                logging.warning("Not upgrading because system.img comes from an unverified source")
                return
        else:
            system_zip = "" # Race prevention
        if os.path.exists(vendor_zip):
            if not helpers.images.validate(args, "vendor_ota", vendor_zip):
                logging.warning("Not upgrading because vendor.img comes from an unverified source")
                return
        else:
            vendor_zip = "" # Race prevention
        helpers.lxc.stop(args)
        helpers.images.umount_rootfs(args)
        helpers.images.replace(args, system_zip, system_time,
                               vendor_zip, vendor_time)
        args.session["background_start"] = "false"
        helpers.images.mount_rootfs(args, args.images_path, args.session)
        helpers.protocol.set_aidl_version(args)
        helpers.lxc.start(args)

    def service_thread():
        while not stopping:
            IHardware.add_service(
                args, enableNFC, enableBluetooth, suspend, reboot, upgrade)

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
