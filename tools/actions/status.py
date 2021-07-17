# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tools.config

def print_status(args):
    cfg = tools.config.load(args)
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        print("Session:\tRUNNING")
        print("Container:\t" + session_cfg["session"]["state"])
        print("Vendor type:\t" + cfg["waydroid"]["vendor_type"])
        print("Session user:\t{}({})".format(
            session_cfg["session"]["user_name"], session_cfg["session"]["user_id"]))
        print("Wayland display:\t" +
                     session_cfg["session"]["wayland_display"])
    else:
        print("Session:\tSTOPPED")
        print("Vendor type:\t" + cfg["waydroid"]["vendor_type"])
