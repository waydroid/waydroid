# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import configparser
import os
import tools.config


def load(args):
    cfg = configparser.ConfigParser()
    if os.path.isfile(args.config):
        cfg.read(args.config)

    if "waydroid" not in cfg:
        cfg["waydroid"] = {}

    for key in tools.config.defaults:
        if key in tools.config.config_keys and key not in cfg["waydroid"]:
            cfg["waydroid"][key] = str(tools.config.defaults[key])

        # We used to save default values in the config, which can *not* be
        # configured in "waydroid init". That doesn't make sense, we always
        # want to use the defaults from tools/config/__init__.py in that case,
        if key not in tools.config.config_keys and key in cfg["waydroid"]:
            logging.debug("Ignored unconfigurable and possibly outdated"
                          " default value from config: {}".format(cfg['waydroid'][key]))
            del cfg["waydroid"][key]

    if "properties" not in cfg:
        cfg["properties"] = {}
    # no default values for property override

    return cfg

def load_channels():
    config_path = tools.config.channels_defaults["config_path"]
    cfg = configparser.ConfigParser()
    if os.path.isfile(config_path):
        cfg.read(config_path)

    if "channels" not in cfg:
        cfg["channels"] = {}

    for key in tools.config.channels_defaults:
        if key in tools.config.channels_config_keys and key not in cfg["channels"]:
            cfg["channels"][key] = str(tools.config.channels_defaults[key])

        if key not in tools.config.channels_config_keys and key in cfg["channels"]:
            logging.debug("Ignored unconfigurable and possibly outdated"
                          " default value from config: {}".format(cfg['channels'][key]))
            del cfg["channels"][key]

    return cfg
