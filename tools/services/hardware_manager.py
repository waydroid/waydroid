# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading
import tools.actions.container_manager
from tools import helpers
from tools.interfaces import IHardware


def start(args):
    def enableNFC(enable):
        logging.debug("Function enableNFC not implemented")

    def enableBluetooth(enable):
        logging.debug("Function enableBluetooth not implemented")

    def suspend():
        tools.actions.container_manager.freeze(args)

    def reboot():
        helpers.lxc.stop(args)
        helpers.lxc.start(args)

    def upgrade(system_zip, system_time, vendor_zip, vendor_time):
        helpers.lxc.stop(args)
        helpers.images.umount_rootfs(args)
        helpers.images.replace(args, system_zip, system_time,
                               vendor_zip, vendor_time)
        helpers.images.mount_rootfs(args, args.images_path)
        helpers.lxc.start(args)

    def service_thread():
        IHardware.add_service(
            args, enableNFC, enableBluetooth, suspend, reboot, upgrade)

    args.hardware_manager = threading.Thread(target=service_thread)
    args.hardware_manager.start()

def stop(args):
    try:
        if args.hardwareLoop:
            args.hardwareLoop.quit()
    except AttributeError:
        logging.debug("Hardware service is not even started")
