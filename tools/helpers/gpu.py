import glob
import os
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
