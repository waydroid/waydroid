# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import zipfile
import json
import hashlib
import shutil
import os
import tools.config
from tools import helpers
from shutil import which

def sha256sum(filename):
    h = hashlib.sha256()
    b = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


def get(args):
    cfg = tools.config.load(args)
    system_ota = cfg["waydroid"]["system_ota"]
    system_request = helpers.http.retrieve(system_ota)
    if system_request[0] != 200:
        raise ValueError(
            "Failed to get system OTA channel: {}, error: {}".format(args.system_ota, system_request[0]))
    system_responses = json.loads(system_request[1].decode('utf8'))["response"]
    if len(system_responses) < 1:
        raise ValueError("No images found on system channel")

    for system_response in system_responses:
        if system_response['datetime'] > int(cfg["waydroid"]["system_datetime"]):
            images_zip = helpers.http.download(
                args, system_response['url'], system_response['filename'], cache=False)
            logging.info("Validating system image")
            if sha256sum(images_zip) != system_response['id']:
                try:
                    os.remove(images_zip)
                except:
                    pass
                raise ValueError("Downloaded system image hash doesn't match, expected: {}".format(
                    system_response['id']))
            logging.info("Extracting to " + args.images_path)
            with zipfile.ZipFile(images_zip, 'r') as zip_ref:
                zip_ref.extractall(args.images_path)
            cfg["waydroid"]["system_datetime"] = str(system_response['datetime'])
            tools.config.save(args, cfg)
            os.remove(images_zip)
            break

    vendor_ota = cfg["waydroid"]["vendor_ota"]
    vendor_request = helpers.http.retrieve(vendor_ota)
    if vendor_request[0] != 200:
        raise ValueError(
            "Failed to get vendor OTA channel: {}, error: {}".format(vendor_ota, vendor_request[0]))
    vendor_responses = json.loads(vendor_request[1].decode('utf8'))["response"]
    if len(vendor_responses) < 1:
        raise ValueError("No images found on vendor channel")

    for vendor_response in vendor_responses:
        if vendor_response['datetime'] > int(cfg["waydroid"]["vendor_datetime"]):
            images_zip = helpers.http.download(
                args, vendor_response['url'], vendor_response['filename'], cache=False)
            logging.info("Validating vendor image")
            if sha256sum(images_zip) != vendor_response['id']:
                try:
                    os.remove(images_zip)
                except:
                    pass
                raise ValueError("Downloaded vendor image hash doesn't match, expected: {}".format(
                    vendor_response['id']))
            logging.info("Extracting to " + args.images_path)
            with zipfile.ZipFile(images_zip, 'r') as zip_ref:
                zip_ref.extractall(args.images_path)
            cfg["waydroid"]["vendor_datetime"] = str(vendor_response['datetime'])
            tools.config.save(args, cfg)
            os.remove(images_zip)
            break
    remove_overlay(args)

def validate(args, channel, image_zip):
    # Verify that the zip comes from the channel
    cfg = tools.config.load(args)
    channel_url = cfg["waydroid"][channel]
    channel_request = helpers.http.retrieve(channel_url)
    if channel_request[0] != 200:
        return False
    channel_responses = json.loads(channel_request[1].decode('utf8'))["response"]
    for build in channel_responses:
        if sha256sum(image_zip) == build['id']:
            return True
    logging.warning(f"Could not verify the image {image_zip} against {channel_url}")
    return False

def replace(args, system_zip, system_time, vendor_zip, vendor_time):
    cfg = tools.config.load(args)
    args.images_path = cfg["waydroid"]["images_path"]
    if os.path.exists(system_zip):
        with zipfile.ZipFile(system_zip, 'r') as zip_ref:
            zip_ref.extractall(args.images_path)
        os.remove(system_zip)
        cfg["waydroid"]["system_datetime"] = str(system_time)
        tools.config.save(args, cfg)
    if os.path.exists(vendor_zip):
        with zipfile.ZipFile(vendor_zip, 'r') as zip_ref:
            zip_ref.extractall(args.images_path)
        os.remove(vendor_zip)
        cfg["waydroid"]["vendor_datetime"] = str(vendor_time)
        tools.config.save(args, cfg)
    remove_overlay(args)

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
