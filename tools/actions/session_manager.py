# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import time
import signal
import sys
import shutil
import tools.config
from tools import services


def start(args, unlocked_cb=None):
    def signal_handler(sig, frame):
        stop(args)
        sys.exit(0)

    home = os.getenv("HOME")
    # the user might accidently end up doing session start from a sudo shell
    if home != "/root" and os.getuid() == 0:
        # prevent it, otherwise we end up with our files being owned by root and the application working not so well
        logging.error("You're running session start as root but home is not /root")
        logging.error("session start should only be run as a regular user")
        logging.error("If you insist on running it as root, ensure HOME is set to /root")
        return 1

    xdg_session = os.getenv("XDG_SESSION_TYPE")
    if xdg_session != "wayland":
        logging.warning('XDG Session is not "wayland"')

    cfg = tools.config.load_session()
    waydroid_data = cfg["session"]["waydroid_data"]
    if not os.path.isdir(waydroid_data):
        os.makedirs(waydroid_data)
    dpi = tools.helpers.props.host_get(args, "ro.sf.lcd_density")
    if dpi == "":
        dpi = os.getenv("GRID_UNIT_PX")
        if dpi is not None:
            dpi = str(int(dpi) * 20)
        else:
            dpi = "0"
    cfg["session"]["lcd_density"] = dpi
    tools.config.save_session(cfg)

    container_state = "IDLE"
    signal.signal(signal.SIGINT, signal_handler)
    while os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        if container_state != session_cfg["session"]["state"]:
            if session_cfg["session"]["state"] == "RUNNING":
                services.user_manager.start(args, unlocked_cb)
                services.clipboard_manager.start(args)
                if unlocked_cb:
                    unlocked_cb = None
            elif session_cfg["session"]["state"] == "STOPPED":
                services.user_manager.stop(args)
                services.clipboard_manager.stop(args)
            container_state = session_cfg["session"]["state"]
        time.sleep(1)
    services.user_manager.stop(args)
    services.clipboard_manager.stop(args)

def stop(args):
    config_path = tools.config.session_defaults["config_path"]
    if os.path.isfile(config_path):
        services.user_manager.stop(args)
        services.clipboard_manager.stop(args)
        os.remove(config_path)
    else:
        logging.error("WayDroid session is not started")
