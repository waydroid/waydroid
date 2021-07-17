# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import zipfile
import requests
import hashlib
import os
import tools.config
from tools import helpers


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
    system_request = requests.get(system_ota)
    if system_request.status_code != 200:
        raise ValueError(
            "Failed to get system OTA channel: {}".format(system_ota))
    system_responses = system_request.json()["response"]
    if len(system_responses) < 1:
        raise ValueError("No images found on system channel")

    for system_response in system_responses:
        if system_response['datetime'] > int(cfg["waydroid"]["system_datetime"]):
            images_zip = helpers.http.download(
                args, system_response['url'], system_response['filename'], cache=False)
            logging.info("Validating system image")
            if sha256sum(images_zip) != system_response['id']:
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
    vendor_request = requests.get(vendor_ota)
    if vendor_request.status_code != 200:
        raise ValueError(
            "Failed to get vendor OTA channel: {}".format(vendor_ota))
    vendor_responses = vendor_request.json()["response"]
    if len(vendor_responses) < 1:
        raise ValueError("No images found on vendor channel")

    for vendor_response in vendor_responses:
        if vendor_response['datetime'] > int(cfg["waydroid"]["vendor_datetime"]):
            images_zip = helpers.http.download(
                args, vendor_response['url'], vendor_response['filename'], cache=False)
            logging.info("Validating vendor image")
            if sha256sum(images_zip) != vendor_response['id']:
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
    helpers.mount.bind_file(args, args.work + "/waydroid.prop",
                            tools.config.defaults["rootfs"] + "/vendor/waydroid.prop")

def umount_rootfs(args):
    helpers.mount.umount_all(args, tools.config.defaults["rootfs"])
