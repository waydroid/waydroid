# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
import tools.config
import dbus

def get_config(args):
    cfg = tools.config.load(args)
    args.arch = cfg["waydroid"]["arch"]
    args.images_path = cfg["waydroid"]["images_path"]
    args.vendor_type = cfg["waydroid"]["vendor_type"]
    args.system_ota = cfg["waydroid"]["system_ota"]
    args.vendor_ota = cfg["waydroid"]["vendor_ota"]
    args.session = None

def migration(args):
    def versiontuple(v):
        return tuple(map(int, (v.split("."))))

    try:
        old_ver = tools.helpers.props.file_get(args, args.work + "/waydroid_base.prop", "waydroid.tools_version")
        if versiontuple(old_ver) <= versiontuple("1.3.4"):
            chmod_paths = ["cache_http", "host-permissions", "lxc", "images", "waydroid_base.prop", "waydroid.prop", "waydroid.cfg"]
            tools.helpers.run.user(args, ["chmod", "-R", "g-w,o-w"] + [os.path.join(args.work, f) for f in chmod_paths], check=False)
            tools.helpers.run.user(args, ["chmod", "g-w,o-w", args.work], check=False)
    except:
        pass

def upgrade(args):
    get_config(args)
    migration(args)
    status = "STOPPED"
    if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
        status = helpers.lxc.status(args)
    if status != "STOPPED":
        logging.info("Stopping container")
        helpers.lxc.stop(args)
        try:
            args.session = tools.helpers.ipc.DBusContainerService().GetSession()
        except dbus.DBusException:
            pass
    helpers.images.umount_rootfs(args)
    helpers.drivers.loadBinderNodes(args)
    if not args.offline:
        if args.images_path not in tools.config.defaults["preinstalled_images_paths"]:
            helpers.images.get(args)
        else:
            logging.info("Upgrade refused because a pre-installed image is detected at {}.".format(args.images_path))
    helpers.drivers.probeAshmemDriver(args)
    helpers.lxc.setup_host_perms(args)
    helpers.lxc.set_lxc_config(args)
    helpers.lxc.make_base_props(args)
    if status != "STOPPED" and args.session:
        logging.info("Starting container")
        helpers.images.mount_rootfs(args, args.images_path, args.session)
        helpers.protocol.set_aidl_version(args)
        helpers.lxc.start(args)
