# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import os
import re
import logging
import glob
import shutil
import platform
import gbinder
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
    make_entry(tools.helpers.gpu.getDriNode(args), "dev/dri/renderD128")

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

    # TUN/TAP device node for VPN
    make_entry("/dev/net/tun", "dev/tun")

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

    # Vibrator
    make_entry("/sys/class/leds/vibrator",
               options="bind,create=dir,optional 0 0")
    make_entry("/sys/devices/virtual/timed_output/vibrator",
               options="bind,create=dir,optional 0 0")

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

    # tmp
    make_entry("tmpfs", "tmp", "tmpfs", "nodev 0 0", False)
    for n in glob.glob("/tmp/run-*"):
        make_entry(n, options="rbind,create=dir,optional 0 0")

    # NFC config
    make_entry("/system/etc/libnfc-nci.conf", options="bind,optional 0 0")

    return nodes

LXC_APPARMOR_PROFILE = "lxc-waydroid"
def get_apparmor_status(args):
    enabled = False
    if shutil.which("aa-status"):
        enabled = (tools.helpers.run.user(args, ["aa-status", "--quiet"], check=False) == 0)
    if not enabled and shutil.which("systemctl"):
        enabled = (tools.helpers.run.user(args, ["systemctl", "is-active", "-q", "apparmor"], check=False) == 0)
    try:
        with open("/sys/kernel/security/apparmor/profiles", "r") as f:
            enabled &= (LXC_APPARMOR_PROFILE in f.read())
    except:
        enabled = False
    return enabled

def set_lxc_config(args):
    lxc_path = tools.config.defaults["lxc"] + "/waydroid"
    lxc_ver = get_lxc_version(args)
    if lxc_ver == 0:
        raise OSError("LXC is not installed")
    config_paths = tools.config.tools_src + "/data/configs/config_"
    seccomp_profile = tools.config.tools_src + "/data/configs/waydroid.seccomp"

    config_snippets = [ config_paths + "base" ]
    # lxc v1 and v2 are bit special because some options got renamed later
    if lxc_ver <= 2:
        config_snippets.append(config_paths + "1")
    else:
        for ver in range(3, 5):
            snippet = config_paths + str(ver)
            if lxc_ver >= ver and os.path.exists(snippet):
                config_snippets.append(snippet)

    command = ["mkdir", "-p", lxc_path]
    tools.helpers.run.user(args, command)
    command = ["sh", "-c", "cat {} > \"{}\"".format(' '.join('"{0}"'.format(w) for w in config_snippets), lxc_path + "/config")]
    tools.helpers.run.user(args, command)
    command = ["sed", "-i", "s/LXCARCH/{}/".format(platform.machine()), lxc_path + "/config"]
    tools.helpers.run.user(args, command)
    command = ["cp", "-fpr", seccomp_profile, lxc_path + "/waydroid.seccomp"]
    tools.helpers.run.user(args, command)
    if get_apparmor_status(args):
        command = ["sed", "-i", "-E", "/lxc.aa_profile|lxc.apparmor.profile/ s/unconfined/{}/g".format(LXC_APPARMOR_PROFILE), lxc_path + "/config"]
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
            if prop != "":
                for lib in ["/odm/lib", "/odm/lib64", "/vendor/lib", "/vendor/lib64", "/system/lib", "/system/lib64"]:
                    hal_file = lib + "/hw/" + hardware + "." + prop + ".so"
                    if os.path.isfile(hal_file):
                        return prop
        return ""

    def find_hidl(intf):
        if args.vendor_type == "MAINLINE":
            return False

        try:
            sm = gbinder.ServiceManager("/dev/hwbinder")
            return intf in sm.list_sync()
        except:
            return False

    props = []

    if not os.path.exists("/dev/ashmem"):
        props.append("sys.use_memfd=true")

    egl = tools.helpers.props.host_get(args, "ro.hardware.egl")
    dri = tools.helpers.gpu.getDriNode(args)

    gralloc = find_hal("gralloc")
    if not gralloc:
        if find_hidl("android.hardware.graphics.allocator@4.0::IAllocator/default"):
            gralloc = "android"
    if not gralloc:
        if dri:
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
    if not vulkan and dri:
        vulkan = tools.helpers.gpu.getVulkanDriver(args, os.path.basename(dri))
    if vulkan:
        props.append("ro.hardware.vulkan=" + vulkan)

    treble = tools.helpers.props.host_get(args, "ro.treble.enabled")
    if treble != "true":
        camera = find_hal("camera")
        if camera != "":
            props.append("ro.hardware.camera=" + camera)
        else:
            if args.vendor_type == "MAINLINE":
                props.append("ro.hardware.camera=v4l2")

    opengles = tools.helpers.props.host_get(args, "ro.opengles.version")
    if opengles == "":
        opengles = "196609"
    props.append("ro.opengles.version=" + opengles)

    if args.images_path not in tools.config.defaults["preinstalled_images_paths"]:
        props.append("waydroid.system_ota=" + args.system_ota)
        props.append("waydroid.vendor_ota=" + args.vendor_ota)
    else:
        props.append("waydroid.updater.disabled=true")

    props.append("waydroid.tools_version=" + tools.config.version)

    if args.vendor_type == "MAINLINE":
        props.append("ro.vndk.lite=true")

    for product in ["brand", "device", "manufacturer", "model", "name"]:
        prop_product = tools.helpers.props.host_get(
            args, "ro.product.vendor." + product)
        if prop_product != "":
            props.append("ro.product.waydroid." + product + "=" + prop_product)
        else:
            if os.path.isfile("/proc/device-tree/" + product):
                with open("/proc/device-tree/" + product) as f:
                    f_value = f.read().strip().rstrip('\x00')
                    if f_value != "":
                        props.append("ro.product.waydroid." +
                                     product + "=" + f_value)

    prop_fp = tools.helpers.props.host_get(args, "ro.vendor.build.fingerprint")
    if prop_fp != "":
        props.append("ro.build.fingerprint=" + prop_fp)

    # now append/override with values in [properties] section of waydroid.cfg
    cfg = tools.config.load(args)
    for k, v in cfg["properties"].items():
        for idx, elem in enumerate(props):
            if (k+"=") in elem:
                props.pop(idx)
        props.append(k+"="+v)

    base_props = open(args.work + "/waydroid_base.prop", "w")
    for prop in props:
        base_props.write(prop + "\n")
    base_props.close()


def setup_host_perms(args):
    if not os.path.exists(tools.config.defaults["host_perms"]):
        os.mkdir(tools.config.defaults["host_perms"])

    treble = tools.helpers.props.host_get(args, "ro.treble.enabled")
    if treble != "true":
        return

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
    subprocess.run(command, env={"PATH": os.environ['PATH'] + ":/system/bin:/vendor/bin"})

def logcat(args):
    if status(args) != "RUNNING":
        logging.error("WayDroid container is {}".format(status(args)))
        return
    command = ["lxc-attach", "-P", tools.config.defaults["lxc"],
               "-n", "waydroid", "--", "/system/bin/logcat"]
    subprocess.run(command)
