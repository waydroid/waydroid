# Copyright 2023 Maximilian Wende
# SPDX-License-Identifier: GPL-3.0-or-later

import tools.helpers.run
import logging
import re
from contextlib import suppress
from shutil import which

def adb_connect(args):
    """
    Creates an android debugging connection from the host system to the
    Waydroid device, if ADB is found on the host system and the device
    has booted.
    """
    # Check if adb exists on the system.
    if not which("adb"):
        raise RuntimeError("Could not find adb")

    # Start and 'warm up' the adb server
    tools.helpers.run.user(args, ["adb", "start-server"])

    ip = get_device_ip_address()
    if not ip:
        raise RuntimeError("Unknown container IP address. Is Waydroid running?")

    tools.helpers.run.user(args, ["adb", "connect", ip])
    logging.info("Established ADB connection to Waydroid device at {}.".format(ip))

def adb_disconnect(args):
    if not which("adb"):
        raise RuntimeError("Could not find adb")

    ip = get_device_ip_address()
    if not ip:
        raise RuntimeError("Unknown container IP address. Was Waydroid ever running?")

    tools.helpers.run.user(args, ["adb", "disconnect", ip])

def get_device_ip_address():
    # The IP address is queried from the DHCP lease file.
    with suppress(IOError):
        with open("/var/lib/misc/dnsmasq.waydroid0.leases") as f:
            match = re.search(r"(\d{1,3}\.){3}\d{1,3}\s", f.read())
            if match:
                return match.group().strip()
