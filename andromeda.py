#!/usr/bin/env python3
# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import os
import sys
import tools

if __name__ == "__main__":
    os.umask(0o0022)
    sys.exit(tools.main())
