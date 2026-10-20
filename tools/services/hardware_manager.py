# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import time
import tools.actions.container_manager
import tools.actions.session_manager
import tools.config
from tools import helpers
from tools.interfaces import IHardware
from tools.services.runner import ServiceRunner

runner = ServiceRunner("Hardware", "hardwareLoop")

def start(args):
    def enableNFC(enable):
        """
        Intentionally unimplemented.

        Android invokes this over the IHardware binder service whenever NFC
        is toggled on/off. It stays a stub because this codebase has no data
        plane between the container's Android NFC stack and the host's NFC
        hardware: there is no HAL or forwarding service for the container to
        reach the host adapter, so toggling the host nfcd from here could
        not make NFC work in Android anyway.

        The former container_manager NFC hacks (stop host nfcd at container
        start, restart it at stop) were a session-scoped workaround for the
        host and container daemons contending over the NFC adapter, not
        toggle-driven control; they were removed together with the TODO that
        marked them. Driving host nfcd from this callback would restart that
        contention: starting it while the container's nfcd is active would
        leave two daemons fighting over one adapter. Real handling belongs
        in a session-scoped or hardware-adaptation layer that owns the NFC
        device and restores host nfcd state at session teardown.
        """
        logging.warning("enableNFC not implemented: host NFC daemon is left untouched")

    def enableBluetooth(enable):
        """
        Intentionally unimplemented, for the same reason as enableNFC: the
        container's Bluetooth stack is self-contained in this codebase (no
        host-side service is wired up for it), so there is nothing to drive
        from this callback.
        """
        logging.warning("enableBluetooth not implemented: container Bluetooth is self-contained")

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
        cfg = tools.config.load(args)
        helpers.images.mount_rootfs(args, cfg["waydroid"]["images_path"], args.session)
        helpers.protocol.set_aidl_version(args)
        helpers.lxc.start(args)

    def shutdownRequest(reason):
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
            tools.actions.container_manager.stop(args)

    runner.start(lambda: IHardware.add_service(
        args, enableNFC, enableBluetooth, suspend, reboot, upgrade, shutdownRequest))

def stop(args):
    runner.stop(args)
