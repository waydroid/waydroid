# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import shutil
import os
import tools.config
from tools import helpers
from shutil import which

def remove_overlay(args):
    if os.path.isdir(tools.config.defaults["overlay_rw"]):
        shutil.rmtree(tools.config.defaults["overlay_rw"])
    if os.path.isdir(tools.config.defaults["overlay_work"]):
        shutil.rmtree(tools.config.defaults["overlay_work"])

def make_prop(args, cfg, full_props_path):
    if not os.path.isfile(args.work + "/waydroid_base.prop"):
        raise RuntimeError("waydroid_base.prop Not found")
    with open(args.work + "/waydroid_base.prop") as f:
        props = f.read().splitlines()
    if not props:
        raise RuntimeError("waydroid_base.prop is broken!!?")

    def add_prop(key, cfg_key):
        value = cfg[cfg_key]
        if value != "None":
            value = value.replace("/mnt/", "/mnt_extra/")
            props.append(key + "=" + value)

    add_prop("waydroid.host.user", "user_name")
    add_prop("waydroid.host.uid", "user_id")
    add_prop("waydroid.host.gid", "group_id")
    add_prop("waydroid.host_data_path", "waydroid_data")
    add_prop("waydroid.background_start", "background_start")
    props.append("waydroid.xdg_runtime_dir=" + tools.config.defaults["container_xdg_runtime_dir"])
    props.append("waydroid.pulse_runtime_path=" + tools.config.defaults["container_pulse_runtime_path"])
    props.append("waydroid.wayland_display=" + tools.config.defaults["container_wayland_display"])
    if which("waydroid-sensord") is None:
        props.append("waydroid.stub_sensors_hal=1")
    dpi = cfg["lcd_density"]
    if dpi != "0":
        props.append("ro.sf.lcd_density=" + dpi)

    width = cfg["width"]
    if width != "0":
        props.append("waydroid.display_width_override=" + width)

    height = cfg["height"]
    if height != "0":
        props.append("waydroid.display_height_override=" + height)

    final_props = open(full_props_path, "w")
    for prop in props:
        final_props.write(prop + "\n")
    final_props.close()
    os.chmod(full_props_path, 0o644)

def mount_rootfs(args, images_dir, session):
    cfg = tools.config.load(args)
    helpers.mount.mount(args, images_dir + "/system.img",
                        tools.config.defaults["rootfs"], umount=True)
    if cfg["waydroid"]["mount_overlays"] == "True":
        try:
            helpers.mount.mount_overlay(args, [tools.config.defaults["overlay"],
                                               tools.config.defaults["rootfs"]],
                                    tools.config.defaults["rootfs"],
                                    upper_dir=tools.config.defaults["overlay_rw"] + "/system",
                                    work_dir=tools.config.defaults["overlay_work"] + "/system")
        except RuntimeError:
            cfg["waydroid"]["mount_overlays"] = "False"
            tools.config.save(args, cfg)
            logging.warning("Mounting overlays failed. The feature has been disabled.")

    helpers.mount.mount(args, images_dir + "/vendor.img",
                           tools.config.defaults["rootfs"] + "/vendor")
    if cfg["waydroid"]["mount_overlays"] == "True":
        helpers.mount.mount_overlay(args, [tools.config.defaults["overlay"] + "/vendor",
                                           tools.config.defaults["rootfs"] + "/vendor"],
                                    tools.config.defaults["rootfs"] + "/vendor",
                                    upper_dir=tools.config.defaults["overlay_rw"] + "/vendor",
                                    work_dir=tools.config.defaults["overlay_work"] + "/vendor")

    for egl_path in ["/vendor/lib/egl", "/vendor/lib64/egl"]:
        if os.path.isdir(egl_path):
            helpers.mount.bind(
                args, egl_path, tools.config.defaults["rootfs"] + egl_path)
    if helpers.mount.ismount("/odm"):
        helpers.mount.bind(
            args, "/odm", tools.config.defaults["rootfs"] + "/odm_extra")
    else:
        if os.path.isdir("/vendor/odm"):
            helpers.mount.bind(
                args, "/vendor/odm", tools.config.defaults["rootfs"] + "/odm_extra")

    make_prop(args, session, args.work + "/waydroid.prop")
    helpers.mount.bind_file(args, args.work + "/waydroid.prop",
                            tools.config.defaults["rootfs"] + "/vendor/waydroid.prop")

def umount_rootfs(args):
    helpers.mount.umount_all(args, tools.config.defaults["rootfs"])
