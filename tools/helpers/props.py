# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from shutil import which
import logging
import os
import tools.helpers.run
from tools.interfaces import IPlatform


def host_get(args, prop):
    if which("getprop") is not None:
        command = ["getprop", prop]
        return tools.helpers.run.user(args, command, output_return=True).strip()
    else:
        return ""

def host_set(args, prop, value):
    if which("setprop") is not None:
        command = ["setprop", prop, value]
        tools.helpers.run.user(args, command)

def get(args, prop):
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        if session_cfg["session"]["state"] == "RUNNING":
            platformService = IPlatform.get_service(args)
            if platformService:
                return platformService.getprop(prop, "")
            else:
                logging.error("Failed to access IPlatform service")
        else:
            logging.error("WayDroid container is {}".format(
                session_cfg["session"]["state"]))
    else:
        logging.error("WayDroid session is stopped")

def set(args, prop, value):
    if os.path.exists(tools.config.session_defaults["config_path"]):
        session_cfg = tools.config.load_session()
        if session_cfg["session"]["state"] == "RUNNING":
            platformService = IPlatform.get_service(args)
            if platformService:
                platformService.setprop(prop, value)
            else:
                logging.error("Failed to access IPlatform service")
        else:
            logging.error("WayDroid container is {}".format(
                session_cfg["session"]["state"]))
    else:
        logging.error("WayDroid session is stopped")
