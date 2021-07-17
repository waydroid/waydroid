# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import requests
from tools import helpers
import tools.config


def get_vendor_type(args):
    vndk_str = helpers.props.host_get(args, "ro.vndk.version")
    ret = "MAINLINE"
    if vndk_str != "":
        vndk = int(vndk_str)
        if vndk > 19:
            ret = "HALIUM_" + str(vndk - 19)

    return ret

def setup_config(args):
    cfg = tools.config.load(args)
    args.arch = helpers.arch.host()
    cfg["waydroid"]["arch"] = args.arch
    cfg["waydroid"]["images_path"] = args.images_path

    channels_cfg = tools.config.load_channels()
    if not args.system_channel:
        args.system_channel = channels_cfg["channels"]["system_channel"]
    if not args.vendor_channel:
        args.vendor_channel = channels_cfg["channels"]["vendor_channel"]
    if not args.rom_type:
        args.rom_type = channels_cfg["channels"]["rom_type"]
    if not args.system_type:
        args.system_type = channels_cfg["channels"]["system_type"]

    args.system_ota = args.system_channel + "/" + args.rom_type + \
        "/waydroid_" + args.arch + "/" + args.system_type + ".json"
    system_request = requests.get(args.system_ota)
    if system_request.status_code != 200:
        raise ValueError(
            "Failed to get system OTA channel: {}".format(args.system_ota))

    device_codename = helpers.props.host_get(args, "ro.product.device")
    args.vendor_type = None
    for vendor in [device_codename, get_vendor_type(args)]:
        vendor_ota = args.vendor_channel + "/waydroid_" + \
            args.arch + "/" + vendor + ".json"
        vendor_request = requests.get(vendor_ota)
        if vendor_request.status_code == 200:
            args.vendor_type = vendor
            args.vendor_ota = vendor_ota
            break

    if not args.vendor_type:
        raise ValueError(
            "Failed to get vendor OTA channel: {}".format(vendor_ota))

    cfg["waydroid"]["vendor_type"] = args.vendor_type
    cfg["waydroid"]["system_ota"] = args.system_ota
    cfg["waydroid"]["vendor_ota"] = args.vendor_ota
    helpers.drivers.setupBinderNodes(args)
    cfg["waydroid"]["binder"] = args.BINDER_DRIVER
    cfg["waydroid"]["vndbinder"] = args.VNDBINDER_DRIVER
    cfg["waydroid"]["hwbinder"] = args.HWBINDER_DRIVER
    tools.config.save(args, cfg)

def init(args):
    if not os.path.isfile(args.config) or args.force:
        setup_config(args)
        status = "STOPPED"
        if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
            status = helpers.lxc.status(args)
        if status != "STOPPED":
            logging.info("Stopping container")
            helpers.lxc.stop(args)
        helpers.images.umount_rootfs(args)
        helpers.images.get(args)
        if not os.path.isdir(tools.config.defaults["rootfs"]):
            os.mkdir(tools.config.defaults["rootfs"])
        helpers.lxc.setup_host_perms(args)
        helpers.lxc.set_lxc_config(args)
        helpers.lxc.make_base_props(args)
        if status != "STOPPED":
            logging.info("Starting container")
            helpers.images.mount_rootfs(args, args.images_path)
            helpers.lxc.start(args)
    else:
        logging.info("Already initialized")
