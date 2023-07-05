# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import platform
import logging

def host():
    machine = platform.machine()

    mapping = {
        "i686": "x86",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "armv7l": "arm",
        "armv8l": "arm"
    }
    if machine in mapping:
        return maybe_remap(mapping[machine])
    raise ValueError("platform.machine '" + machine + "'"
                     " architecture is not supported")

def maybe_remap(target):
    if target == "x86_64":
        with open("/proc/cpuinfo") as f:
            if "sse4_2" not in f.read():
                logging.info("x86_64 CPU does not support SSE4.2, falling back to x86...")
                return "x86"
    elif target == "arm64" and platform.architecture()[0] == "32bit":
        return "arm"

    return target
