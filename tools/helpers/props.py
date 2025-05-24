# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from shutil import which
import subprocess
import logging
import tools.helpers.run
from tools.interfaces import IPlatform


def host_get(args, prop):
    if which("getprop") is not None:
        command = ["getprop", prop]
        return subprocess.run(command, stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
    else:
        return ""

def host_set(args, prop, value):
    if which("setprop") is not None:
        command = ["setprop", prop, value]
        tools.helpers.run.user(args, command)

def get(args, prop):
    platformService = IPlatform.get_service(args)
    if platformService:
        return platformService.getprop(prop, "")
    else:
        logging.error("Failed to access IPlatform service")

def set(args, prop, value):
    platformService = IPlatform.get_service(args)
    if platformService:
        platformService.setprop(prop, value)
    else:
        logging.error("Failed to access IPlatform service")

def file_get(args, file, prop):
    with open(file) as build_prop:
        for line in build_prop:
            line = line.strip()
            if len(line) == 0 or line[0] == "#":
                continue
            k,v = line.partition("=")[::2]
            if k == prop:
                return v
    return ""
