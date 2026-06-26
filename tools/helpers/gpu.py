import glob
import os
from contextlib import suppress
import tools.helpers.props

unsupported = ["nvidia"]

def getMinor(args, dev):
    return tools.helpers.props.file_get(args, f"/sys/class/drm/{dev}/uevent", "MINOR")

def getKernelDriver(args, dev):
    return tools.helpers.props.file_get(args, f"/sys/class/drm/{dev}/device/uevent", "DRIVER")

def getCardFromRender(args, dev):
    try:
        return "/dev/dri/" + os.path.basename(sorted(glob.glob(f"/sys/class/drm/{dev}/device/drm/card*"))[0])
    except IndexError:
        return ""

def getDriNode(args):
    cfg = tools.config.load(args)
    node = cfg["waydroid"].get("drm_device")
    if node:
        if not os.path.exists(node):
            raise OSError(f"The specified drm_device {node} does not exist")
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
        "panfrost": "panfrost",
        "msm": "freedreno",
        "msm_dpu": "freedreno",
        "vc4": "broadcom",
        "nouveau": "nouveau",
    }
    kernel_driver = getKernelDriver(args, dev)

    if kernel_driver == "i915":
        with suppress(Exception):
            dev = os.path.basename(getCardFromRender(args, dev))
            gen = tools.helpers.run.user(args, ["awk", "/^graphics version:|^gen:/ {print $NF}",
                f"/sys/kernel/debug/dri/{getMinor(args, dev)}/i915_capabilities"], output_return=True, check=False)
            if int(gen) < 9:
                return "intel_hasvk"

    if kernel_driver in mapping:
        return mapping[kernel_driver]
    return ""
