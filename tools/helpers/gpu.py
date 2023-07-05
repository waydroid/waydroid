import glob
import os
import tools.helpers.props

unsupported = ["nvidia", "nouveau"]

def getKernelDriver(args, dev):
    return tools.helpers.props.file_get(args, "/sys/class/drm/{}/device/uevent".format(dev), "DRIVER")

def getCardFromRender(args, dev):
    try:
        return "/dev/dri/" + os.path.basename(glob.glob("/sys/class/drm/{}/device/drm/card*".format(dev))[0])
    except IndexError:
        return ""

def getDriNode(args):
    for node in glob.glob("/dev/dri/renderD*"):
        renderDev = os.path.basename(node)
        if getKernelDriver(args, renderDev) not in unsupported:
            return node, getCardFromRender(args, renderDev)
    return "", ""

def getVulkanDriver(args, dev):
    mapping = {
        "i915": "intel",
        "amdgpu": "radeon",
        "radeon": "radeon",
        "panfrost": "panfrost",
        "msm": "freedreno",
        "vc4": "broadcom",
    }
    kernel_driver = getKernelDriver(args, dev)
    if kernel_driver in mapping:
        return mapping[kernel_driver]
    return ""
