from tools import helpers
import tools.config
import logging

# Call me with rootfs mounted!
def set_aidl_version(args):
    cfg = tools.config.load(args)
    android_api = 0
    try:
        android_api = int(helpers.props.file_get(args,
                tools.config.defaults["rootfs"] + "/system/build.prop",
                "ro.build.version.sdk"))
    except:
        logging.error("Failed to parse android version from system.img")

    if android_api < 28:
        binder_protocol = "aidl"
        sm_protocol =     "aidl"
    elif android_api < 30:
        binder_protocol = "aidl2"
        sm_protocol =     "aidl2"
    elif android_api < 31:
        binder_protocol = "aidl3"
        sm_protocol =     "aidl3"
    elif android_api < 33:
        binder_protocol = "aidl4"
        sm_protocol = "aidl3"
    else:
        binder_protocol = "aidl3"
        sm_protocol =     "aidl3"

    cfg["waydroid"]["binder_protocol"] = binder_protocol
    cfg["waydroid"]["service_manager_protocol"] = sm_protocol
    tools.config.save(args, cfg)
