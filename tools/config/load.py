# Copyright 2021 Oliver Smith
# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import configparser
import os
import tools.config

def load(args):
    cfg = configparser.ConfigParser()
    if os.path.isfile(args.config):
        cfg.read(args.config)

    if "andromeda" not in cfg:
        cfg["andromeda"] = {}

    for key in tools.config.defaults:
        if key in tools.config.config_keys and key not in cfg["andromeda"]:
            cfg["andromeda"][key] = str(tools.config.defaults[key])

        # We used to save default values in the config, which can *not* be
        # configured in "andromeda init". That doesn't make sense, we always
        # want to use the defaults from tools/config/__init__.py in that case,
        if key not in tools.config.config_keys and key in cfg["andromeda"]:
            logging.debug("Ignored unconfigurable and possibly outdated"
                          " default value from config: {}".format(cfg['andromeda'][key]))
            del cfg["andromeda"][key]

    if "properties" not in cfg:
        cfg["properties"] = {}
    # no default values for property override

    return cfg
