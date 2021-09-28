# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import os
import re
import logging
import glob
import shutil
import platform
import tools.config
import tools.helpers.run


def get_lxc_version(args):
    if shutil.which("lxc-info") is not None:
        command = ["lxc-info", "--version"]
        version_str = tools.helpers.run.user(args, command, output_return=True)
        return int(version_str[0])
    else:
        return 0


def generate_nodes_lxc_config(args):
    def make_entry(src, dist=None, mnt_type="none", options="bind,create=file,optional 0 0", check=True):
        if check and not os.path.exists(src):
            return False
        entry = "lxc.mount.entry = "
        entry += src + " "
        if dist is None:
            dist = src[1:]
        entry += dist + " "
        entry += mnt_type + " "
        entry += options
        nodes.append(entry)
        return True

    nodes = []
    # Necessary dev nodes
    make_entry("tmpfs", "dev", "tmpfs", "nosuid 0 0", False)
    make_entry("/dev/zero")
    make_entry("/dev/null")
    make_entry("/dev/full")
    make_entry("/dev/ashmem", check=False)
    make_entry("/dev/fuse")
    make_entry("/dev/ion")
    make_entry("/dev/char", options="bind,create=dir,optional 0 0")

    # Graphic dev nodes
    make_entry("/dev/kgsl-3d0")
    make_entry("/dev/mali0")
    make_entry("/dev/pvr_sync")
    make_entry("/dev/pmsg0")
    make_entry("/dev/dxg")
    make_entry("/dev/dri", options="bind,create=dir,optional 0 0")

    for n in glob.glob("/dev/fb*"):
        make_entry(n)
    for n in glob.glob("/dev/graphics/fb*"):
        make_entry(n)
    for n in glob.glob("/dev/video*"):
        make_entry(n)

    # Binder dev nodes
    make_entry("/dev/" + args.BINDER_DRIVER, "dev/binder", check=False)
    make_entry("/dev/" + args.VNDBINDER_DRIVER, "dev/vndbinder", check=False)
    make_entry("/dev/" + args.HWBINDER_DRIVER, "dev/hwbinder", check=False)

    if args.vendor_type != "MAINLINE":
        if not make_entry("/dev/hwbinder", "dev/host_hwbinder"):
            raise OSError('Binder node "hwbinder" of host not found')
        make_entry("/vendor", "vendor_extra", options="bind,optional 0 0")

    # Necessary device nodes for adb
    make_entry("none", "dev/pts", "devpts", "defaults,mode=644,ptmxmode=666,create=dir 0 0", False)
    make_entry("/dev/uhid")

    # Low memory killer sys node
    make_entry("/sys/module/lowmemorykiller", options="bind,create=dir,optional 0 0")

    # Mount /data
    make_entry("tmpfs", "mnt", "tmpfs", "mode=0755,uid=0,gid=1000", False)
    make_entry(tools.config.defaults["data"], "data", options="bind 0 0", check=False)

    # Mount host permissions
    make_entry(tools.config.defaults["host_perms"],
               "vendor/etc/host-permissions", options="bind,optional 0 0")

    # Recursive mount /run to provide necessary host sockets
    make_entry("/run", options="rbind,create=dir 0 0")

    # Necessary sw_sync node for HWC
    make_entry("/dev/sw_sync")
    make_entry("/sys/kernel/debug", options="rbind,create=dir,optional 0 0")

    # Media dev nodes (for Mediatek)
    make_entry("/dev/Vcodec")
    make_entry("/dev/MTK_SMI")
    make_entry("/dev/mdp_sync")
    make_entry("/dev/mtk_cmdq")

    # WSLg
    make_entry("tmpfs", "mnt_extra", "tmpfs", "nodev 0 0", False)
    make_entry("/mnt/wslg", "mnt_extra/wslg",
               options="rbind,create=dir,optional 0 0")

    # var
    make_entry("tmpfs", "var", "tmpfs", "nodev 0 0", False)
    make_entry("/var/run", options="rbind,create=dir,optional 0 0")

    return nodes


def set_lxc_config(args):
    lxc_path = tools.config.defaults["lxc"] + "/waydroid"
    config_file = "config_2"
    lxc_ver = get_lxc_version(args)
    if lxc_ver == 0:
        raise OSError("LXC is not installed")
    elif lxc_ver <= 2:
        config_file = "config_1"
    config_path = tools.config.tools_src + "/data/configs/" + config_file

    command = ["mkdir", "-p", lxc_path]
    tools.helpers.run.user(args, command)
    command = ["cp", "-fpr", config_path, lxc_path + "/config"]
    tools.helpers.run.user(args, command)
    command = ["sed", "-i", "s/LXCARCH/{}/".format(platform.machine()), lxc_path + "/config"]
    tools.helpers.run.user(args, command)

    nodes = generate_nodes_lxc_config(args)
    config_nodes_tmp_path = args.work + "/config_nodes"
    config_nodes = open(config_nodes_tmp_path, "w")
    for node in nodes:
        config_nodes.write(node + "\n")
    config_nodes.close()
    command = ["mv", config_nodes_tmp_path, lxc_path]
    tools.helpers.run.user(args, command)


def make_base_props(args):
    def find_hal(hardware):
        hardware_props = [
            "ro.hardware." + hardware,
            "ro.hardware",
            "ro.product.board",
            "ro.arch",
            "ro.board.platform"]
        for p in hardware_props:
            prop = tools.helpers.props.host_get(args, p)
            hal_prop = ""
            if prop != "":
                for lib in ["lib", "lib64"]:
                    hal_file = "/vendor/" + lib + "/hw/" + hardware + "." + prop + ".so"
                    command = ["readlink", "-f", hal_file]
                    hal_file_path = tools.helpers.run.user(args, command, output_return=True).strip()
                    if os.path.isfile(hal_file_path):
                        hal_prop = re.sub(".*" + hardware + ".", "", hal_file_path)
                        hal_prop = re.sub(".so", "", hal_prop)
                        if hal_prop != "":
                            return hal_prop
            if hal_prop != "":
                return hal_prop
        return ""

    props = []
    egl = tools.helpers.props.host_get(args, "ro.hardware.egl")

    gralloc = find_hal("gralloc")
    if gralloc == "":
        if os.path.exists("/dev/dri"):
            gralloc = "gbm"
            egl = "mesa"
        else:
            gralloc = "default"
            egl = "swiftshader"
        props.append("debug.stagefright.ccodec=0")
    props.append("ro.hardware.gralloc=" + gralloc)

    if egl != "":
        props.append("ro.hardware.egl=" + egl)

    media_profiles = tools.helpers.props.host_get(args, "media.settings.xml")
    if media_profiles != "":
        media_profiles = media_profiles.replace("vendor/", "vendor_extra/")
        media_profiles = media_profiles.replace("odm/", "odm_extra/")
        props.append("media.settings.xml=" + media_profiles)

    ccodec = tools.helpers.props.host_get(args, "debug.stagefright.ccodec")
    if ccodec != "":
        props.append("debug.stagefright.ccodec=" + ccodec)

    ext_library = tools.helpers.props.host_get(args, "ro.vendor.extension_library")
    if ext_library != "":
        ext_library = ext_library.replace("vendor/", "vendor_extra/")
        ext_library = ext_library.replace("odm/", "odm_extra/")
        props.append("ro.vendor.extension_library=" + ext_library)

    vulkan = find_hal("vulkan")
    if vulkan != "":
        props.append("ro.hardware.vulkan=" + vulkan)

    opengles = tools.helpers.props.host_get(args, "ro.opengles.version")
    if opengles == "":
        opengles = "196608"
    props.append("ro.opengles.version=" + opengles)

    props.append("waydroid.system_ota=" + args.system_ota)
    props.append("waydroid.vendor_ota=" + args.vendor_ota)
    props.append("waydroid.tools_version=" + tools.config.version)

    if args.vendor_type == "MAINLINE":
        props.append("ro.vndk.lite=true")
        props.append("ro.hardware.camera=v4l2")

    base_props = open(args.work + "/waydroid_base.prop", "w")
    for prop in props:
        base_props.write(prop + "\n")
    base_props.close()


def setup_host_perms(args):
    sku = tools.helpers.props.host_get(args, "ro.boot.product.hardware.sku")
    copy_list = []
    copy_list.extend(
        glob.glob("/vendor/etc/permissions/android.hardware.nfc.*"))
    if os.path.exists("/vendor/etc/permissions/android.hardware.consumerir.xml"):
        copy_list.append("/vendor/etc/permissions/android.hardware.consumerir.xml")
    copy_list.extend(
        glob.glob("/odm/etc/permissions/android.hardware.nfc.*"))
    if os.path.exists("/odm/etc/permissions/android.hardware.consumerir.xml"):
        copy_list.append("/odm/etc/permissions/android.hardware.consumerir.xml")
    if sku != "":
        copy_list.extend(
            glob.glob("/odm/etc/permissions/sku_{}/android.hardware.nfc.*".format(sku)))
        if os.path.exists("/odm/etc/permissions/sku_{}/android.hardware.consumerir.xml".format(sku)):
            copy_list.append(
                "/odm/etc/permissions/sku_{}/android.hardware.consumerir.xml".format(sku))

    if not os.path.exists(tools.config.defaults["host_perms"]):
        os.mkdir(tools.config.defaults["host_perms"])

    for filename in copy_list:
        shutil.copy(filename, tools.config.defaults["host_perms"])

def status(args):
    command = ["lxc-info", "-P", tools.config.defaults["lxc"], "-n", "waydroid", "-sH"]
    out = subprocess.run(command, stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
    os.chmod(args.log, 0o666)
    return out

def start(args):
    command = ["lxc-start", "-P", tools.config.defaults["lxc"],
               "-F", "-n", "waydroid", "--", "/init"]
    tools.helpers.run.user(args, command, output="background")

def stop(args):
    command = ["lxc-stop", "-P",
               tools.config.defaults["lxc"], "-n", "waydroid", "-k"]
    tools.helpers.run.user(args, command)

def freeze(args):
    command = ["lxc-freeze", "-P", tools.config.defaults["lxc"], "-n", "waydroid"]
    tools.helpers.run.user(args, command)

def unfreeze(args):
    command = ["lxc-unfreeze", "-P",
               tools.config.defaults["lxc"], "-n", "waydroid"]
    tools.helpers.run.user(args, command)

def shell(args):
    if status(args) != "RUNNING":
        logging.error("WayDroid container is {}".format(status(args)))
        return
    command = ["lxc-attach", "-P", tools.config.defaults["lxc"],
               "-n", "waydroid", "--"]
    if args.COMMAND:
        command.append(args.COMMAND)
    else:
        command.append("/system/bin/sh")
    subprocess.run(command, env={"PATH": os.environ['PATH'] + "/system/bin:/vendor/bin"})

def logcat(args):
    if status(args) != "RUNNING":
        logging.error("WayDroid container is {}".format(status(args)))
        return
    command = ["lxc-attach", "-P", tools.config.defaults["lxc"],
               "-n", "waydroid", "--", "/system/bin/logcat"]
    subprocess.run(command)
