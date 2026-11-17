#!/usr/bin/env python3
# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import os
import sys

try:
    import tools
except ModuleNotFoundError as e:
    print("Waydroid could not start: the Python module '{}' is not installed.".format(e.name),
          file=sys.stderr)
    print("Install the corresponding package (e.g. python3-{}).".format(e.name.split(".")[0]),
          file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    os.umask(0o0022)
    sys.exit(tools.main())
