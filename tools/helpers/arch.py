# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import platform
import logging
import ctypes

def is_32bit_capable():
    # man 2 personality
    personality = ctypes.CDLL(None).personality
    personality.restype = ctypes.c_int
    personality.argtypes = [ctypes.c_ulong]
    # linux/include/uapi/linux/personality.h
    PER_LINUX32 = 0x0008
    # mirror e.g. https://github.com/util-linux/util-linux/blob/v2.41/sys-utils/lscpu-cputype.c#L745-L756
    pers = personality(PER_LINUX32)
    if pers != -1: # success, revert back to previous persona (typically just PER_LINUX, 0x0000)
        personality(pers)
        return True
    return False # unable to "impersonate" 32-bit host, nothing done

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
    if target.startswith("x86"):
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()
        if "ssse3" not in cpuinfo:
            raise ValueError("x86/x86_64 CPU must support SSSE3!")
        if target == "x86_64" and "sse4_2" not in cpuinfo:
            logging.info("x86_64 CPU does not support SSE4.2, falling back to x86...")
            return "x86"
    elif target == "arm64" and platform.architecture()[0] == "32bit":
        return "arm"
    elif target == "arm64" and not is_32bit_capable():
        logging.info("AArch64 CPU does not appear to support AArch32, assuming arm64_only...")
        return "arm64_only"

    return target
