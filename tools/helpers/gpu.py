import glob
import os
import tools.helpers.props

unsupported = ["nvidia"]

def getKernelDriver(args, dev):
    return tools.helpers.props.file_get(args, "/sys/class/drm/{}/device/uevent".format(dev), "DRIVER")

def getDriNode(args):
    for node in glob.glob("/dev/dri/renderD*"):
        dev = os.path.basename(node)
        if getKernelDriver(args, dev) not in unsupported:
            return node
    return ""

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
