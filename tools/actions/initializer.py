# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
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

    preinstalled_images = tools.config.defaults["preinstalled_images_path"]
    if not args.images_path:
        if os.path.isdir(preinstalled_images):
            if os.path.isfile(preinstalled_images + "/system.img") and os.path.isfile(preinstalled_images + "/vendor.img"):
                args.images_path = preinstalled_images
            else:
                logging.error("Missing system or vendor on preinstalled images dir, fallback to default")
    if not args.images_path:
        args.images_path = tools.config.defaults["images_path"]
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
    system_request = helpers.http.retrieve(args.system_ota)
    if system_request[0] != 200:
        if args.images_path != preinstalled_images:
            raise ValueError(
                "Failed to get system OTA channel: {}, error: {}".format(args.system_ota, system_request[0]))
        else:
            args.system_ota = "None"

    device_codename = helpers.props.host_get(args, "ro.product.device")
    args.vendor_type = None
    for vendor in [device_codename, get_vendor_type(args)]:
        vendor_ota = args.vendor_channel + "/waydroid_" + \
            args.arch + "/" + vendor + ".json"
        vendor_request = helpers.http.retrieve(vendor_ota)
        if vendor_request[0] == 200:
            args.vendor_type = vendor
            args.vendor_ota = vendor_ota
            break

    if not args.vendor_type:
        if args.images_path != preinstalled_images:
            raise ValueError(
                "Failed to get vendor OTA channel: {}".format(vendor_ota))
        else:
            args.vendor_ota = "None"
            args.vendor_type = get_vendor_type(args)

    cfg["waydroid"]["vendor_type"] = args.vendor_type
    cfg["waydroid"]["system_ota"] = args.system_ota
    cfg["waydroid"]["vendor_ota"] = args.vendor_ota
    helpers.drivers.setupBinderNodes(args)
    cfg["waydroid"]["binder"] = args.BINDER_DRIVER
    cfg["waydroid"]["vndbinder"] = args.VNDBINDER_DRIVER
    cfg["waydroid"]["hwbinder"] = args.HWBINDER_DRIVER
    tools.config.save(args, cfg)

def init(args):
    if not os.path.isfile(args.config) or not os.path.isdir(tools.config.defaults["rootfs"]) or args.force:
        setup_config(args)
        status = "STOPPED"
        if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
            status = helpers.lxc.status(args)
        if status != "STOPPED":
            logging.info("Stopping container")
            helpers.lxc.stop(args)
        helpers.images.umount_rootfs(args)
        if args.images_path != tools.config.defaults["preinstalled_images_path"]:
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
