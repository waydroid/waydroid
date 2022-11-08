# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import glob
import fcntl
import struct
import tools.config
import tools.helpers.run


BINDER_DRIVERS = [
    "anbox-binder",
    "puddlejumper",
    "bonder",
    "binder"
]
VNDBINDER_DRIVERS = [
    "anbox-vndbinder",
    "vndpuddlejumper",
    "vndbonder",
    "vndbinder"
]
HWBINDER_DRIVERS = [
    "anbox-hwbinder",
    "hwpuddlejumper",
    "hwbonder",
    "hwbinder"
]


def isBinderfsLoaded(args):
    with open("/proc/filesystems", "r") as handle:
        for line in handle:
            words = line.split()
            if len(words) >= 2 and words[1] == "binder":
                return True

    return False

def allocBinderNodes(args, binder_dev_nodes):
    NRBITS = 8
    TYPEBITS = 8
    SIZEBITS = 14
    NRSHIFT = 0
    TYPESHIFT = NRSHIFT + NRBITS
    SIZESHIFT = TYPESHIFT + TYPEBITS
    DIRSHIFT = SIZESHIFT + SIZEBITS
    WRITE = 0x1
    READ = 0x2

    def IOC(direction, _type, nr, size):
        return (direction << DIRSHIFT) | (_type << TYPESHIFT) | (nr << NRSHIFT) | (size << SIZESHIFT)

    def IOWR(_type, nr, size):
        return IOC(READ|WRITE, _type, nr, size)

    BINDER_CTL_ADD = IOWR(98, 1, 264)
    binderctrlfd = open('/dev/binderfs/binder-control','rb')

    for node in binder_dev_nodes:
        node_struct = struct.pack(
            '256sII', bytes(node, 'utf-8'), 0, 0)
        try:
            fcntl.ioctl(binderctrlfd.fileno(), BINDER_CTL_ADD, node_struct)
        except FileExistsError:
            pass

def probeBinderDriver(args):
    binder_dev_nodes = []
    has_binder = False
    has_vndbinder = False
    has_hwbinder = False
    for node in BINDER_DRIVERS:
        if os.path.exists("/dev/" + node):
            has_binder = True
    if not has_binder:
        binder_dev_nodes.append(BINDER_DRIVERS[0])
    for node in VNDBINDER_DRIVERS:
        if os.path.exists("/dev/" + node):
            has_vndbinder = True
    if not has_vndbinder:
        binder_dev_nodes.append(VNDBINDER_DRIVERS[0])
    for node in HWBINDER_DRIVERS:
        if os.path.exists("/dev/" + node):
            has_hwbinder = True
    if not has_hwbinder:
        binder_dev_nodes.append(HWBINDER_DRIVERS[0])

    if len(binder_dev_nodes) > 0:
        if not isBinderfsLoaded(args):
            devices = ','.join(binder_dev_nodes)
            command = ["modprobe", "binder_linux",
                       "devices=\"{}\"".format(devices)]
            output = tools.helpers.run.user(args, command, check=False, output_return=True)
            if output:
                logging.error("Failed to load binder driver")
                logging.error(output.strip())

        if isBinderfsLoaded(args):
            command = ["mkdir", "-p", "/dev/binderfs"]
            tools.helpers.run.user(args, command, check=False)
            command = ["mount", "-t", "binder", "binder", "/dev/binderfs"]
            tools.helpers.run.user(args, command, check=False)
            allocBinderNodes(args, binder_dev_nodes)
            command = ["ln", "-s"]
            command.extend(glob.glob("/dev/binderfs/*"))
            command.append("/dev/")
            tools.helpers.run.user(args, command, check=False)

    return 0

def probeAshmemDriver(args):
    if not os.path.exists("/dev/ashmem"):
        command = ["modprobe", "-q", "ashmem_linux"]
        tools.helpers.run.user(args, command, check=False)

    if not os.path.exists("/dev/ashmem"):
        return -1
    
    return 0

def setupBinderNodes(args):
    has_binder = False
    has_vndbinder = False
    has_hwbinder = False
    if args.vendor_type == "MAINLINE":
        probeBinderDriver(args)
        for node in BINDER_DRIVERS:
            if os.path.exists("/dev/" + node):
                has_binder = True
                args.BINDER_DRIVER = node
        if not has_binder:
            raise OSError('Binder node "binder" for waydroid not found')

        for node in VNDBINDER_DRIVERS:
            if os.path.exists("/dev/" + node):
                has_vndbinder = True
                args.VNDBINDER_DRIVER = node
        if not has_vndbinder:
            raise OSError('Binder node "vndbinder" for waydroid not found')

        for node in HWBINDER_DRIVERS:
            if os.path.exists("/dev/" + node):
                has_hwbinder = True
                args.HWBINDER_DRIVER = node
        if not has_hwbinder:
            raise OSError('Binder node "hwbinder" for waydroid not found')
    else:
        for node in BINDER_DRIVERS[:-1]:
            if os.path.exists("/dev/" + node):
                has_binder = True
                args.BINDER_DRIVER = node
        if not has_binder:
            raise OSError('Binder node "binder" for waydroid not found')

        for node in VNDBINDER_DRIVERS[:-1]:
            if os.path.exists("/dev/" + node):
                has_vndbinder = True
                args.VNDBINDER_DRIVER = node
        if not has_vndbinder:
            raise OSError('Binder node "vndbinder" for waydroid not found')

        for node in HWBINDER_DRIVERS[:-1]:
            if os.path.exists("/dev/" + node):
                has_hwbinder = True
                args.HWBINDER_DRIVER = node
        if not has_hwbinder:
            raise OSError('Binder node "hwbinder" for waydroid not found')

def loadBinderNodes(args):
    cfg = tools.config.load(args)
    args.BINDER_DRIVER = cfg["waydroid"]["binder"]
    args.VNDBINDER_DRIVER = cfg["waydroid"]["vndbinder"]
    args.HWBINDER_DRIVER = cfg["waydroid"]["hwbinder"]
    # These might not be in cfg on package upgrade
    args.BINDER_PROTOCOL = cfg["waydroid"].get("binder_protocol")
    args.SERVICE_MANAGER_PROTOCOL = cfg["waydroid"].get("service_manager_protocol")
