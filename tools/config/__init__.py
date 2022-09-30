# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import pwd

#
# Exported functions
#
from tools.config.load import load, load_session, load_channels
from tools.config.save import save, save_session

#
# Exported variables (internal configuration)
#
version = "1.3.3"
tools_src = os.path.normpath(os.path.realpath(__file__) + "/../../..")

# Keys saved in the config file (mostly what we ask in 'waydroid init')
config_keys = ["arch",
               "images_path",
               "vendor_type",
               "system_datetime",
               "vendor_datetime",
               "suspend_action"]

session_config_keys = ["user_name",
                       "user_id",
                       "group_id",
                       "host_user",
                       "xdg_data_home",
                       "waydroid_data",
                       "xdg_runtime_dir",
                       "wayland_display",
                       "pulse_runtime_path",
                       "state",
                       "lcd_density"]

# Config file/commandline default values
# $WORK gets replaced with the actual value for args.work (which may be
# overridden on the commandline)
defaults = {
    "arch": "arm64",
    "work": "/var/lib/waydroid",
    "vendor_type": "MAINLINE",
    "system_datetime": "0",
    "vendor_datetime": "0",
    "preinstalled_images_paths": [
        "/etc/waydroid-extra/images",
        "/usr/share/waydroid-extra/images",
    ],
    "suspend_action": "freeze"
}
defaults["images_path"] = defaults["work"] + "/images"
defaults["rootfs"] = defaults["work"] + "/rootfs"
defaults["data"] = defaults["work"] + "/data"
defaults["lxc"] = defaults["work"] + "/lxc"
defaults["host_perms"] = defaults["work"] + "/host-permissions"

session_defaults = {
    "user_name": pwd.getpwuid(os.getuid()).pw_name,
    "user_id": str(os.getuid()),
    "group_id": str(os.getgid()),
    "host_user": os.path.expanduser("~"),
    "xdg_data_home": str(os.environ.get('XDG_DATA_HOME', os.path.expanduser("~") + "/.local/share")),
    "xdg_runtime_dir": str(os.environ.get('XDG_RUNTIME_DIR')),
    "wayland_display": str(os.environ.get('WAYLAND_DISPLAY')),
    "pulse_runtime_path": str(os.environ.get('PULSE_RUNTIME_PATH')),
    "state": "STOPPED",
    "lcd_density": "0"
}
session_defaults["config_path"] = defaults["work"] + "/session.cfg"
session_defaults["waydroid_data"] = session_defaults["xdg_data_home"] + \
    "/waydroid/data"
if session_defaults["pulse_runtime_path"] == "None":
    session_defaults["pulse_runtime_path"] = session_defaults["xdg_runtime_dir"] + "/pulse"

channels_defaults = {
    "config_path": "/usr/share/waydroid-extra/channels.cfg",
    "system_channel": "https://ota.waydro.id/system",
    "vendor_channel": "https://ota.waydro.id/vendor",
    "rom_type": "lineage",
    "system_type": "VANILLA"
}
channels_config_keys = ["system_channel",
                        "vendor_channel",
                        "rom_type",
                        "system_type"]
