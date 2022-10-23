# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import zipfile
import json
import hashlib
import os
import tools.config
from tools import helpers
from shutil import which
from shutil import copyfile

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

def replace(args, system_zip, system_time, vendor_zip, vendor_time):
    cfg = tools.config.load(args)
    args.images_path = cfg["waydroid"]["images_path"]
    if os.path.exists(system_zip):
        with zipfile.ZipFile(system_zip, 'r') as zip_ref:
            zip_ref.extractall(args.images_path)
        cfg["waydroid"]["system_datetime"] = str(system_time)
        tools.config.save(args, cfg)
    if os.path.exists(vendor_zip):
        with zipfile.ZipFile(vendor_zip, 'r') as zip_ref:
            zip_ref.extractall(args.images_path)
        cfg["waydroid"]["vendor_datetime"] = str(vendor_time)
        tools.config.save(args, cfg)

def make_prop(args, full_props_path):
    if not os.path.isfile(args.work + "/waydroid_base.prop"):
        raise RuntimeError("waydroid_base.prop Not found")
    with open(args.work + "/waydroid_base.prop") as f:
        props = f.read().splitlines()
    if not props:
        raise RuntimeError("waydroid_base.prop is broken!!?")

    session_cfg = tools.config.load_session()

    def add_prop(key, cfg_key):
        value = session_cfg["session"][cfg_key]
        if value != "None":
            value = value.replace("/mnt/", "/mnt_extra/")
            props.append(key + "=" + value)

    add_prop("waydroid.host.user", "user_name")
    add_prop("waydroid.host.uid", "user_id")
    add_prop("waydroid.host.gid", "group_id")
    add_prop("waydroid.xdg_runtime_dir", "xdg_runtime_dir")
    add_prop("waydroid.pulse_runtime_path", "pulse_runtime_path")
    add_prop("waydroid.wayland_display", "wayland_display")
    if which("waydroid-sensord") is None:
        props.append("waydroid.stub_sensors_hal=1")
    dpi = session_cfg["session"]["lcd_density"]
    if dpi != "0":
        props.append("ro.sf.lcd_density=" + dpi)

    final_props = open(full_props_path, "w")
    for prop in props:
        final_props.write(prop + "\n")
    final_props.close()
    os.chmod(full_props_path, 0o644)

def make_camera_hal_config(args, full_camera_hal_config_path):
    if not os.path.isfile(args.work + "/camera_hal.yaml"):
        raise RuntimeError("camera_hal.yaml Not found")
    with open(args.work + "/camera_hal.yaml") as f:
        props = f.read().splitlines()
    if not props:
        raise RuntimeError("camera_hal.yaml is broken!!?")

    copyfile(args.work + "/camera_hal.yaml", full_camera_hal_config_path)
    os.chmod(full_camera_hal_config_path, 0o644)

def mount_rootfs(args, images_dir):
    helpers.mount.mount(args, images_dir + "/system.img",
                        tools.config.defaults["rootfs"], umount=True)
    helpers.mount.mount(args, images_dir + "/vendor.img",
                           tools.config.defaults["rootfs"] + "/vendor")
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

    make_prop(args, args.work + "/waydroid.prop")
    helpers.mount.bind_file(args, args.work + "/waydroid.prop",
                            tools.config.defaults["rootfs"] + "/vendor/waydroid.prop")
    if os.path.exists(args.work + "/camera_hal.yaml"):
        helpers.mount.bind_file(args, args.work + "/camera_hal.yaml",
                                tools.config.defaults["rootfs"] +
                                "/vendor/etc/libcamera/camera_hal.yaml")
    else:
        print("ERROR!!!! ERRRROROOOORRR")
        logging.error((f"Camera config {args.work}/camera_hal.yaml not found.\n"
                       "Most internal cameras need this to work in Waydroid."))
        raise RuntimeException("Camera config not found!")
    print("No error!")

def umount_rootfs(args):
    helpers.mount.umount_all(args, tools.config.defaults["rootfs"])
