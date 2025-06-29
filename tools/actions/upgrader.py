# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
from tools.helpers.version import versiontuple
import tools.config

def get_config(args):
    cfg = tools.config.load(args)
    args.arch = cfg["waydroid"]["arch"]
    args.images_path = cfg["waydroid"]["images_path"]
    args.vendor_type = cfg["waydroid"]["vendor_type"]
    args.system_ota = cfg["waydroid"]["system_ota"]
    args.vendor_ota = cfg["waydroid"]["vendor_ota"]
    args.session = None

def migration(args):
    try:
        old_ver = tools.helpers.props.file_get(args, args.work + "/waydroid_base.prop", "waydroid.tools_version")
        if versiontuple(old_ver) <= versiontuple("1.3.4"):
            chmod_paths = ["cache_http", "host-permissions", "lxc", "images", "rootfs", "data", "waydroid_base.prop", "waydroid.prop", "waydroid.cfg"]
            tools.helpers.run.user(args, ["chmod", "-R", "g-w,o-w"] + [os.path.join(args.work, f) for f in chmod_paths], check=False)
            tools.helpers.run.user(args, ["chmod", "g-w,o-w", args.work], check=False)
            os.remove(os.path.join(args.work, "session.cfg"))
        if versiontuple(old_ver) <= versiontuple("1.6.0"):
            # Because we now default adb to secure, disable auto_adb to avoid prompting the user on every session startup
            cfg = tools.config.load(args)
            cfg["waydroid"]["auto_adb"] = "False"
            tools.config.save(args, cfg)
    except:
        pass

def upgrade(args):
    get_config(args)
    status = "STOPPED"
    if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
        status = helpers.lxc.status(args)
    if status != "STOPPED":
        logging.info("Stopping container")
        try:
            container = tools.helpers.ipc.DBusContainerService()
            args.session = container.GetSession()
            container.Stop(False)
        except Exception as e:
            logging.debug(e)
            tools.actions.container_manager.stop(args)
    migration(args)
    helpers.drivers.loadBinderNodes(args)
    if not args.offline:
        if args.images_path not in tools.config.defaults["preinstalled_images_paths"]:
            helpers.images.get(args)
        else:
            logging.info("Upgrade refused because Waydroid was configured to load pre-installed image from {}.".format(args.images_path))
    helpers.drivers.probeAshmemDriver(args)
    helpers.lxc.setup_host_perms(args)
    helpers.lxc.set_lxc_config(args)
    helpers.lxc.make_base_props(args)
    if status != "STOPPED":
        logging.info("Starting container")
        try:
            container.Start(args.session)
        except Exception as e:
            logging.debug(e)
            logging.error("Failed to restart container. Please do so manually.")
