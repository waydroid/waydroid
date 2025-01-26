# Copyright 2021 Erfan Abdi
# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
from tools import helpers
import tools.config

import sys
import shutil
import threading
import subprocess
import configparser
import multiprocessing
import select
import queue
import time
import dbus
import dbus.service
from gi.repository import GLib

def is_mounted(path):
    with open('/proc/mounts', 'r') as f:
        for line in f:
            if path in line.split():
                return True
    return False

def migrate_installation():
    source_path = "/var/lib/waydroid"
    if not os.path.exists(source_path):
        return False
    try:
        rootfs_path = os.path.join(source_path, "rootfs")
        if is_mounted(rootfs_path):
            subprocess.run(["lxc-stop", "-P", os.path.join(source_path, "lxc"), "-n", "waydroid", "-k"],
                           check=False, stderr=subprocess.PIPE)

            subprocess.run(["umount", "-l", rootfs_path],
                           check=False, stderr=subprocess.PIPE)

        dest_path = tools.config.defaults["work"]
        if os.path.exists(os.path.join(dest_path, "andromeda.cfg")):
            return False

        os.makedirs(dest_path, exist_ok=True)

        file_renames = {
            "waydroid.cfg": "andromeda.cfg",
            "waydroid.prop": "andromeda.prop",
            "waydroid_base.prop": "andromeda_base.prop"
        }

        for src_name, dst_name in file_renames.items():
            src_file = os.path.join(source_path, src_name)
            dst_file = os.path.join(dest_path, dst_name)
            if os.path.exists(src_file):
                if src_name == "waydroid.cfg":
                    config = configparser.ConfigParser()
                    config.read(src_file)
                    if "waydroid" in config.sections():
                        section_content = dict(config["waydroid"])
                        config.remove_section("waydroid")
                        config.add_section("andromeda")
                        for key, value in section_content.items():
                            if key == "images_path":
                                config.set("andromeda", key, "/usr/share/andromeda-images")
                            else:
                                config.set("andromeda", key, value)
                    with open(dst_file, "w") as configfile:
                        config.write(configfile)
                else:
                    shutil.copy2(src_file, dst_file)

        src_lxc_dir = os.path.join(source_path, "lxc", "waydroid")
        dst_lxc_dir = os.path.join(dest_path, "lxc", "andromeda")

        if os.path.exists(src_lxc_dir):
            os.makedirs(os.path.dirname(dst_lxc_dir), exist_ok=True)

            shutil.copytree(src_lxc_dir, dst_lxc_dir, dirs_exist_ok=True)

            src_seccomp = os.path.join(dst_lxc_dir, "waydroid.seccomp")
            dst_seccomp = os.path.join(dst_lxc_dir, "andromeda.seccomp")
            if os.path.exists(src_seccomp):
                shutil.move(src_seccomp, dst_seccomp)

            config_file = os.path.join(dst_lxc_dir, "config")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    content = f.read()

                content = content.replace("# Waydroid LXC Config", "# Andromeda LXC Config")
                content = content.replace("/var/lib/waydroid/", "/var/lib/andromeda/")
                content = content.replace("waydroid.seccomp", "andromeda.seccomp")
                content = content.replace("waydroid0", "andromeda0")
                content = content.replace("lxc.uts.name = waydroid", "lxc.uts.name = andromeda")
                content = content.replace("/lxc/waydroid/", "/lxc/andromeda/")

                with open(config_file, 'w') as f:
                    f.write(content)

            config_nodes_file = os.path.join(dst_lxc_dir, "config_nodes")
            if os.path.exists(config_nodes_file):
                with open(config_nodes_file, 'r') as f:
                    content = f.read()

                content = content.replace("/var/lib/waydroid/", "/var/lib/andromeda/")

                with open(config_nodes_file, 'w') as f:
                    f.write(content)

            config_session_file = os.path.join(dst_lxc_dir, "config_session")
            if os.path.exists(config_session_file):
                with open(config_session_file, 'r') as f:
                    content = f.read()

                content = content.replace("/var/lib/waydroid/", "/var/lib/andromeda/")
                content = content.replace("waydroid", "andromeda")

                with open(config_session_file, 'w') as f:
                    f.write(content)

        for item in os.listdir(source_path):
            if item in file_renames or item == "lxc":
                continue

            s = os.path.join(source_path, item)
            d = os.path.join(dest_path, item)

            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        return True
    except Exception as e:
        return False

def is_initialized(args):
    return os.path.isfile(args.config) and os.path.isdir(tools.config.defaults["rootfs"])

def get_vendor_type(args):
    vndk_str = helpers.props.host_get(args, "ro.vndk.version")
    ret = "MAINLINE"
    if vndk_str != "":
        vndk = int(vndk_str)
        if vndk > 19:
            halium_ver = vndk - 19
            if vndk > 31:
                halium_ver -= 1 # 12L -> Halium 12
            ret = "HALIUM_" + str(halium_ver)
            if vndk == 32:
                ret += "L"

    return ret

def setup_config(args):
    cfg = tools.config.load(args)
    args.arch = helpers.arch.host()
    cfg["andromeda"]["arch"] = args.arch

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
    cfg["andromeda"]["images_path"] = args.images_path

    device_codename = helpers.props.host_get(args, "ro.product.device")
    args.vendor_type = get_vendor_type(args)

    cfg["andromeda"]["vendor_type"] = args.vendor_type
    helpers.drivers.setupBinderNodes(args)
    cfg["andromeda"]["binder"] = args.BINDER_DRIVER
    cfg["andromeda"]["vndbinder"] = args.VNDBINDER_DRIVER
    cfg["andromeda"]["hwbinder"] = args.HWBINDER_DRIVER
    tools.config.save(args, cfg)

def init(args):
    if not is_initialized(args) or args.force:
        setup_config(args)
        status = "STOPPED"
        if os.path.exists(tools.config.defaults["lxc"] + "/andromeda"):
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
