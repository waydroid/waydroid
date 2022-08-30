# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
import tools.config


def get_config(args):
    cfg = tools.config.load(args)
    args.arch = cfg["waydroid"]["arch"]
    args.images_path = cfg["waydroid"]["images_path"]
    args.vendor_type = cfg["waydroid"]["vendor_type"]
    args.system_ota = cfg["waydroid"]["system_ota"]
    args.vendor_ota = cfg["waydroid"]["vendor_ota"]

def upgrade(args):
    get_config(args)
    status = "STOPPED"
    if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
        status = helpers.lxc.status(args)
    if status != "STOPPED":
        logging.info("Stopping container")
        helpers.lxc.stop(args)
    helpers.images.umount_rootfs(args)
    helpers.drivers.loadBinderNodes(args)
    if not args.offline:
        preinstalled_images_path = tools.config.defaults["preinstalled_images_path"]
        if args.images_path != preinstalled_images_path:
            helpers.images.get(args)
        else:
            logging.info("Upgrade refused because a pre-installed image is detected at {}.".format(preinstalled_images_path))
    helpers.lxc.setup_host_perms(args)
    helpers.lxc.set_lxc_config(args)
    helpers.lxc.make_base_props(args)
    if status != "STOPPED":
        logging.info("Starting container")
        helpers.images.mount_rootfs(args, args.images_path)
        helpers.protocol.set_aidl_version(args)
        helpers.lxc.start(args)
