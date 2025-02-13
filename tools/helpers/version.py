# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re

def versiontuple(v):
    return tuple(map(int, (v.split("."))))

def kernel_version():
    return tuple(map(int, re.match(r"(\d+)\.(\d+)", os.uname().release).groups()))
