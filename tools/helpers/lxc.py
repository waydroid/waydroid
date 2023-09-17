# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import os
import logging
import glob
import shutil
import time
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

def add_node_entry(nodes, src, dist, mnt_type, options, check):
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

def generate_nodes_lxc_config(args):
    nodes = []
    def make_entry(src, dist=None, mnt_type="none", options="bind,create=file,optional 0 0", check=True):
        return add_node_entry(nodes, src, dist, mnt_type, options, check)

    # Necessary dev nodes
    make_entry("tmpfs", "dev", "tmpfs", "nosuid 0 0", False)
    make_entry("/dev/zero")
    make_entry("/dev/null")
    make_entry("/dev/full")
    make_entry("/dev/ashmem")
    make_entry("/dev/fuse")
    make_entry("/dev/ion")
    make_entry("/dev/tty")
    make_entry("/dev/char", options="bind,create=dir,optional 0 0")

    # Graphic dev nodes
    make_entry("/dev/kgsl-3d0")
    make_entry("/dev/mali0")
    make_entry("/dev/pvr_sync")
    make_entry("/dev/pmsg0")
    make_entry("/dev/dxg")
    render, _ = tools.helpers.gpu.getDriNode(args)
    make_entry(render)

    for n in glob.glob("/dev/fb*"):
        make_entry(n)
    for n in glob.glob("/dev/graphics/fb*"):
        make_entry(n)
    for n in glob.glob("/dev/video*"):
        make_entry(n)
    for n in glob.glob("/dev/dma_heap/*"):
        make_entry(n)

    # Binder dev nodes
    make_entry("/dev/" + args.BINDER_DRIVER, "dev/binder", check=False)
    make_entry("/dev/" + args.VNDBINDER_DRIVER, "dev/vndbinder", check=False)
    make_entry("/dev/" + args.HWBINDER_DRIVER, "dev/hwbinder", check=False)

    if args.vendor_type != "MAINLINE":
        if not make_entry("/dev/hwbinder", "dev/host_hwbinder"):
            raise OSError('Binder node "hwbinder" of host not found')
        make_entry("/vendor", "vendor_extra", options="rbind,optional 0 0")

    # Necessary device nodes for adb
    make_entry("none", "dev/pts", "devpts", "defaults,mode=644,ptmxmode=666,create=dir 0 0", False)
    make_entry("/dev/uhid")

    # TUN/TAP device node for VPN
    make_entry("/dev/net/tun", "dev/tun")

    # Low memory killer sys node
    make_entry("/sys/module/lowmemorykiller", options="bind,create=dir,optional 0 0")

    # Mount host permissions
    make_entry(tools.config.defaults["host_perms"],
               "vendor/etc/host-permissions", options="bind,optional 0 0")

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

    # Make a tmpfs at every possible rootfs mountpoint
    make_entry("tmpfs", "tmp", "tmpfs", "nodev 0 0", False)
    make_entry("tmpfs", "var", "tmpfs", "nodev 0 0", False)
    make_entry("tmpfs", "run", "tmpfs", "nodev 0 0", False)

    # NFC config
    make_entry("/system/etc/libnfc-nci.conf", options="bind,optional 0 0")

    return nodes

LXC_APPARMOR_PROFILE = "lxc-waydroid"
def get_apparmor_status(args):
    enabled = False
    if shutil.which("aa-enabled"):
        enabled = (tools.helpers.run.user(args, ["aa-enabled", "--quiet"], check=False) == 0)
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

    # Create empty file
    open(os.path.join(lxc_path, "config_session"), mode="w").close()

def generate_session_lxc_config(args, session):
    nodes = []
    def make_entry(src, dist=None, mnt_type="none", options="rbind,create=file 0 0"):
        if any(x in src for x in ["\n", "\r"]):
            logging.warning("User-provided mount path contains illegal character: " + src)
            return False
        if dist is None and (not os.path.exists(src) or
                             str(os.stat(src).st_uid) != session["user_id"]):
            logging.warning("User-provided mount path is not owned by user: " + src)
            return False
        return add_node_entry(nodes, src, dist, mnt_type, options, check=False)

    # Make sure XDG_RUNTIME_DIR exists
    if not make_entry("tmpfs", tools.config.defaults["container_xdg_runtime_dir"], options="create=dir 0 0"):
        raise OSError("Failed to create XDG_RUNTIME_DIR mount point")

    wayland_host_socket = os.path.realpath(os.path.join(session["xdg_runtime_dir"], session["wayland_display"]))
    wayland_container_socket = os.path.realpath(os.path.join(tools.config.defaults["container_xdg_runtime_dir"], tools.config.defaults["container_wayland_display"]))
    if not make_entry(wayland_host_socket, wayland_container_socket[1:]):
        raise OSError("Failed to bind Wayland socket")

    # Make sure PULSE_RUNTIME_DIR exists
    pulse_host_socket = os.path.join(session["pulse_runtime_path"], "native")
    pulse_container_socket = os.path.join(tools.config.defaults["container_pulse_runtime_path"], "native")
    make_entry(pulse_host_socket, pulse_container_socket[1:])

    if not make_entry(session["waydroid_data"], "data", options="rbind 0 0"):
        raise OSError("Failed to bind userdata")

    lxc_path = tools.config.defaults["lxc"] + "/waydroid"
    config_nodes_tmp_path = args.work + "/config_session"
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

    # Added for security reasons
    props.append("ro.adb.secure=1")
    props.append("ro.debuggable=0")

    egl = tools.helpers.props.host_get(args, "ro.hardware.egl")
    dri, _ = tools.helpers.gpu.getDriNode(args)

    gralloc = find_hal("gralloc")
    if not gralloc:
        if find_hidl("android.hardware.graphics.allocator@4.0::IAllocator/default"):
            gralloc = "android"
    if not gralloc:
        if dri:
            gralloc = "gbm"
            egl = "mesa"
            props.append("gralloc.gbm.device=" + dri)
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
        opengles = "196610"
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
    try:
        return tools.helpers.run.user(args, command, output_return=True).strip()
    except:
        logging.info("Couldn't get LXC status. Assuming STOPPED.")
        return "STOPPED"

def wait_for_running(args):
    lxc_status = status(args)
    timeout = 10
    while lxc_status != "RUNNING" and timeout > 0:
        lxc_status = status(args)
        logging.info(
            "waiting {} seconds for container to start...".format(timeout))
        timeout = timeout - 1
        time.sleep(1)
    if lxc_status != "RUNNING":
        raise OSError("container failed to start")

def start(args):
    command = ["lxc-start", "-P", tools.config.defaults["lxc"],
               "-F", "-n", "waydroid", "--", "/init"]
    tools.helpers.run.user(args, command, output="background")
    wait_for_running(args)
    # Workaround lxc-start changing stdout/stderr permissions to 700
    os.chmod(args.log, 0o666)

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

ANDROID_ENV = {
    "PATH": "/product/bin:/apex/com.android.runtime/bin:/apex/com.android.art/bin:/system_ext/bin:/system/bin:/system/xbin:/odm/bin:/vendor/bin:/vendor/xbin",
    "ANDROID_ROOT": "/system",
    "ANDROID_DATA": "/data",
    "ANDROID_STORAGE": "/storage",
    "ANDROID_ART_ROOT": "/apex/com.android.art",
    "ANDROID_I18N_ROOT": "/apex/com.android.i18n",
    "ANDROID_TZDATA_ROOT": "/apex/com.android.tzdata",
    "ANDROID_RUNTIME_ROOT": "/apex/com.android.runtime",
    "BOOTCLASSPATH": "/apex/com.android.art/javalib/core-oj.jar:/apex/com.android.art/javalib/core-libart.jar:/apex/com.android.art/javalib/core-icu4j.jar:/apex/com.android.art/javalib/okhttp.jar:/apex/com.android.art/javalib/bouncycastle.jar:/apex/com.android.art/javalib/apache-xml.jar:/system/framework/framework.jar:/system/framework/ext.jar:/system/framework/telephony-common.jar:/system/framework/voip-common.jar:/system/framework/ims-common.jar:/system/framework/framework-atb-backward-compatibility.jar:/apex/com.android.conscrypt/javalib/conscrypt.jar:/apex/com.android.media/javalib/updatable-media.jar:/apex/com.android.mediaprovider/javalib/framework-mediaprovider.jar:/apex/com.android.os.statsd/javalib/framework-statsd.jar:/apex/com.android.permission/javalib/framework-permission.jar:/apex/com.android.sdkext/javalib/framework-sdkextensions.jar:/apex/com.android.wifi/javalib/framework-wifi.jar:/apex/com.android.tethering/javalib/framework-tethering.jar"
}

def android_env_attach_options(args):
    local_env = ANDROID_ENV.copy()
    # Include CLASSPATH env that was generated by Android
    command = ["lxc-attach", "-P", tools.config.defaults["lxc"],
               "-n", "waydroid", "--clear-env", "--",
               "/system/bin/cat" ,"/data/system/environ/classpath"]
    allowed = ["CLASSPATH", "SYSTEMSERVER"]
    try:
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out, _ = p.communicate()
        if p.returncode == 0:
            for line in out.decode().splitlines():
                _, k, v = line.split(' ', 2)
                if any(pattern in k for pattern in allowed):
                    local_env[k] = v
    except:
        pass
    env = [k + "=" + v for k, v in local_env.items()]
    return [x for var in env for x in ("--set-var", var)]

def shell(args):
    state = status(args)
    if state == "FROZEN":
        unfreeze(args)
    elif state != "RUNNING":
        logging.error("WayDroid container is {}".format(state))
        return
    command = ["lxc-attach", "-P", tools.config.defaults["lxc"],
               "-n", "waydroid", "--clear-env"]
    command.extend(android_env_attach_options(args))
    if args.uid!=None:
        command.append("--uid="+str(args.uid))
    if args.gid!=None:
        command.append("--gid="+str(args.gid))
    elif args.uid!=None:
        command.append("--gid="+str(args.uid))
    if args.nolsm or args.allcaps or args.nocgroup:
        elevatedprivs = "--elevated-privileges="
        addpipe = False
        if args.nolsm:
            if addpipe:
                elevatedprivs+="|"
            elevatedprivs+="LSM"
            addpipe = True
        if args.allcaps:
            if addpipe:
                elevatedprivs+="|"
            elevatedprivs+="CAP"
            addpipe = True
        if args.nocgroup:
            if addpipe:
                elevatedprivs+="|"
            elevatedprivs+="CGROUP"
            addpipe = True
        command.append(elevatedprivs)
    if args.context!=None and not args.nolsm:
        command.append("--context="+args.context)
    command.append("--")
    if args.COMMAND:
        command.extend(args.COMMAND)
    else:
        command.append("/system/bin/sh")

    try:
        subprocess.run(command)
    except KeyboardInterrupt:
        pass

    if state == "FROZEN":
        freeze(args)

def logcat(args):
    args.COMMAND = ["/system/bin/logcat"]
    args.uid = None
    args.gid = None
    args.nolsm = None
    args.allcaps = None
    args.nocgroup = None
    args.context = None
    shell(args)
