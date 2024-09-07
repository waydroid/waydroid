# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
from tools.helpers.version import versiontuple
import tools.config
import dbus

def get_config(args):
    cfg = tools.config.load(args)
    args.arch = cfg["waydroid"]["arch"]
    args.images_path = cfg["waydroid"]["images_path"]
    args.vendor_type = cfg["waydroid"]["vendor_type"]
    args.session = None

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
    helpers.drivers.loadBinderNodes(args)
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
