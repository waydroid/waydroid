# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import platform

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
        return mapping[machine]
    raise ValueError("platform.machine '" + machine + "'"
                     " architecture is not supported")
