# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import logging
import tools.config


def save(args, cfg):
    logging.debug("Save config: " + args.config)
    os.makedirs(os.path.dirname(args.config), 0o700, True)
    with open(args.config, "w") as handle:
        cfg.write(handle)

def save_session(cfg):
    config_path = tools.config.session_defaults["config_path"]
    logging.debug("Save session config: " + config_path)
    os.makedirs(os.path.dirname(config_path), 0o700, True)
    with open(config_path, "w") as handle:
        cfg.write(handle)
