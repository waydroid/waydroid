# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import logging


def save(args, cfg):
    logging.debug("Save config: " + args.config)
    os.makedirs(os.path.dirname(args.config), 0o700, True)
    with open(args.config, "w") as handle:
        cfg.write(handle)
