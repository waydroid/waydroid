import glob
import logging
import os
import shutil
import subprocess
import tools.config
import tools.helpers.props

unsupported = ["nvidia"]

def getMinor(args, dev):
    return tools.helpers.props.file_get(args, "/sys/class/drm/{}/uevent".format(dev), "MINOR")

def getKernelDriver(args, dev):
    return tools.helpers.props.file_get(args, "/sys/class/drm/{}/device/uevent".format(dev), "DRIVER")

def getCardFromRender(args, dev):
    try:
        return "/dev/dri/" + os.path.basename(sorted(glob.glob("/sys/class/drm/{}/device/drm/card*".format(dev)))[0])
    except IndexError:
        return ""

def getDriNode(args):
    cfg = tools.config.load(args)
    node = cfg["waydroid"].get("drm_device")
    if node:
        if not os.path.exists(node):
            raise OSError("The specified drm_device {} does not exist".format(node))
        renderDev = os.path.basename(node)
        if getKernelDriver(args, renderDev) not in unsupported:
            return node, getCardFromRender(args, renderDev)
        return "", ""

    for node in sorted(glob.glob("/dev/dri/renderD*")):
        renderDev = os.path.basename(node)
        if getKernelDriver(args, renderDev) not in unsupported:
            return node, getCardFromRender(args, renderDev)
    return "", ""

def getVulkanDriver(args, dev):
    mapping = {
        "i915": "intel",
        "xe": "intel",
        "amdgpu": "radeon",
        "radeon": "radeon",
        "panfrost": "panfrost",
        "msm": "freedreno",
        "msm_dpu": "freedreno",
        "vc4": "broadcom",
        "nouveau": "nouveau",
    }
    kernel_driver = getKernelDriver(args, dev)

    if kernel_driver == "i915":
        try:
            dev = os.path.basename(getCardFromRender(args, dev))
            gen = tools.helpers.run.user(args,["awk", "/^graphics version:|^gen:/ {print $NF}",
                "/sys/kernel/debug/dri/{}/i915_capabilities".format(getMinor(args, dev))], output_return=True, check=False)
            if int(gen) < 9:
                return "intel_hasvk"
        except:
            pass

    if kernel_driver in mapping:
        return mapping[kernel_driver]
    return ""

def installVulkanCompatLayer(args):
    # Install VkLayer_waydroid_compat into vendor overlay to mask
    # ETC2/EAC formats on Intel GPUs (prevents AHB crash)
    layer_dir = os.path.join(tools.config.defaults["overlay"], "vendor",
                             "lib64", "vulkan")
    data_dir = os.path.join(tools.config.tools_src, "data")

    layer_so = "VkLayer_waydroid_compat.so"
    layer_json = "VkLayer_waydroid_compat.json"
    layer_src = "VkLayer_waydroid_compat.c"

    src_c = os.path.join(data_dir, layer_src)
    src_so = os.path.join(data_dir, layer_so)
    src_json = os.path.join(data_dir, layer_json)

    # Build the .so from source if it doesn't exist yet
    if not os.path.isfile(src_so):
        if not os.path.isfile(src_c):
            logging.warning("Vulkan compat layer source not found at %s",
                            src_c)
            return
        logging.info("Building Vulkan compat layer from source...")
        try:
            subprocess.check_call(
                ["cc", "-shared", "-fPIC", "-O2", "-o", src_so, src_c],
                stderr=subprocess.STDOUT)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logging.warning("Failed to build Vulkan compat layer. "
                            "Install a C compiler (gcc or clang) and "
                            "vulkan headers, then retry")
            return

    os.makedirs(layer_dir, exist_ok=True)

    shutil.copy2(src_so, os.path.join(layer_dir, layer_so))
    if os.path.isfile(src_json):
        shutil.copy2(src_json, os.path.join(layer_dir, layer_json))
    logging.info("Installed Vulkan compat layer to %s", layer_dir)

