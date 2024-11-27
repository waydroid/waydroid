# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
import tools.config

import sys
import threading
import multiprocessing
import select
import queue
import time
import dbus
import dbus.service
from gi.repository import GLib

def is_initialized(args):
    return os.path.isfile(args.config) and os.path.isdir(tools.config.defaults["rootfs"])

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

    preinstalled_images_paths = tools.config.defaults["preinstalled_images_paths"]
    if not args.images_path:
        for preinstalled_images in preinstalled_images_paths:
            if os.path.isdir(preinstalled_images):
                if os.path.isfile(preinstalled_images + "/system.img") and os.path.isfile(preinstalled_images + "/vendor.img"):
                    args.images_path = preinstalled_images
                    break
                else:
                    logging.warning("Found directory {} but missing system or vendor image, ignoring...".format(preinstalled_images))

    if not args.images_path:
        args.images_path = tools.config.defaults["images_path"]
    cfg["waydroid"]["images_path"] = args.images_path

    device_codename = helpers.props.host_get(args, "ro.product.device")
    args.vendor_type = get_vendor_type(args)

    cfg["waydroid"]["vendor_type"] = args.vendor_type
    helpers.drivers.setupBinderNodes(args)
    cfg["waydroid"]["binder"] = args.BINDER_DRIVER
    cfg["waydroid"]["vndbinder"] = args.VNDBINDER_DRIVER
    cfg["waydroid"]["hwbinder"] = args.HWBINDER_DRIVER
    tools.config.save(args, cfg)

def init(args):
    if not is_initialized(args) or args.force:
        setup_config(args)
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
        helpers.images.remove_overlay(args)
        if not os.path.isdir(tools.config.defaults["rootfs"]):
            os.mkdir(tools.config.defaults["rootfs"])
        if not os.path.isdir(tools.config.defaults["overlay"]):
            os.mkdir(tools.config.defaults["overlay"])
            os.mkdir(tools.config.defaults["overlay"]+"/vendor")
        if not os.path.isdir(tools.config.defaults["overlay_rw"]):
            os.mkdir(tools.config.defaults["overlay_rw"])
            os.mkdir(tools.config.defaults["overlay_rw"]+"/system")
            os.mkdir(tools.config.defaults["overlay_rw"]+"/vendor")
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
    else:
        logging.info("Already initialized")

def wait_for_init(args):
    while not is_initialized(args):
        time.sleep(1)
    return True
