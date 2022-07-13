import glob
import os
import tools.helpers.props

unsupported = ["nvidia"]

def getDriNode(args):
    for node in glob.glob("/dev/dri/renderD*"):
        dev = os.path.basename(node)
        driver = tools.helpers.props.file_get(args, "/sys/class/drm/{}/device/uevent".format(dev), "DRIVER")
        if driver not in unsupported:
            return node
    return ""
