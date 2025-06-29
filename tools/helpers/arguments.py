# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse

try:
    import argcomplete
except ImportError:
    argcomplete = False

import tools.config

""" This file is about parsing command line arguments passed to waydroid, as
    well as generating the help pages (waydroid -h). All this is done with
    Python's argparse. The parsed arguments get extended and finally stored in
    the "args" variable, which is prominently passed to most functions all
    over the waydroid code base.

    See tools/helpers/args.py for more information about the args variable. """

def arguments_init(subparser):
    ret = subparser.add_parser("init", help="set up waydroid specific"
                               " configs and install images")
    ret.add_argument("-i", "--images_path",
                        help="custom path to waydroid images (default in"
                             " /var/lib/waydroid/images)")
    ret.add_argument("-f", "--force", action="store_true",
                     help="re-initialize configs and images")
    ret.add_argument("-c", "--system_channel",
                     help="custom system channel (options: OTA channel URL; default is Official OTA server)")
    ret.add_argument("-v", "--vendor_channel",
                     help="custom vendor channel (options: OTA channel URL; default is Official OTA server)")
    ret.add_argument("-r", "--rom_type",
                     help="rom type (options: \"lineage\", \"bliss\" or OTA channel URL; default is LineageOS)")
    ret.add_argument("-s", "--system_type",
                     help="system type (options: VANILLA, FOSS or GAPPS; default is VANILLA)")
    return ret

def arguments_status(subparser):
    ret = subparser.add_parser("status",
                               help="quick check for the waydroid")
    return ret

def arguments_upgrade(subparser):
    ret = subparser.add_parser("upgrade", help="upgrade images")
    ret.add_argument("-o", "--offline", action="store_true",
                     help="just for updating configs")
    return ret

def arguments_log(subparser):
    ret = subparser.add_parser("log", help="follow the waydroid logfile")
    ret.add_argument("-n", "--lines", default="60",
                     help="count of initial output lines")
    ret.add_argument("-c", "--clear", help="clear the log",
                     action="store_true", dest="clear_log")
    return ret

def arguments_session(subparser):
    ret = subparser.add_parser("session", help="session controller")
    sub = ret.add_subparsers(title="subaction", dest="subaction")
    sub.add_parser("start", help="start session")
    sub.add_parser("stop", help="stop session")
    return ret

def arguments_container(subparser):
    ret = subparser.add_parser("container", help="container controller")
    sub = ret.add_subparsers(title="subaction", dest="subaction")
    sub.add_parser("start", help="start container")
    sub.add_parser("stop", help="stop container")
    sub.add_parser("restart", help="restart container")
    sub.add_parser("freeze", help="freeze container")
    sub.add_parser("unfreeze", help="unfreeze container")
    return ret

def arguments_app(subparser):
    ret = subparser.add_parser("app", help="applications controller")
    sub = ret.add_subparsers(title="subaction", dest="subaction")
    install = sub.add_parser(
        "install", help="push a single package to the container and install it")
    install.add_argument('PACKAGE', help="path to apk file")
    remove = sub.add_parser(
        "remove", help="remove single app package from the container")
    remove.add_argument('PACKAGE', help="package name of app to remove")
    launch = sub.add_parser("launch", help="start single application")
    launch.add_argument('PACKAGE', help="package name of app to launch")
    intent = sub.add_parser("intent", help="start single application")
    intent.add_argument('ACTION', help="action name")
    intent.add_argument('URI', help="data uri")
    sub.add_parser("list", help="list installed applications")
    return ret

def arguments_prop(subparser):
    ret = subparser.add_parser("prop", help="android properties controller")
    sub = ret.add_subparsers(title="subaction", dest="subaction")
    get = sub.add_parser(
        "get", help="get value of property from container")
    get.add_argument('key', help="key of the property to get")
    set = sub.add_parser(
        "set", help="set value to property on container")
    set.add_argument('key', help="key of the property to set")
    set.add_argument('value', help="value of the property to set")
    return ret

def arguments_fullUI(subparser):
    ret = subparser.add_parser("show-full-ui", help="show android full screen in window")
    return ret

def arguments_firstLaunch(subparser):
    ret = subparser.add_parser("first-launch", help="initialize waydroid and start it")
    return ret

def arguments_shell(subparser):
    ret = subparser.add_parser("shell", help="run remote shell command")
    ret.add_argument("-u", "--uid", help="the UID to run as (also sets GID to the same value if -g is not set)")
    ret.add_argument("-g", "--gid", help="the GID to run as")
    ret.add_argument("-s", "--context", help="transition to the specified SELinux or AppArmor security context. No-op if -L is supplied.")
    ret.add_argument("-L", "--nolsm", action="store_true", help="tell LXC not to perform security domain transition related to mandatory access control (e.g. SELinux, AppArmor). If this option is supplied, LXC won't apply a container-wide seccomp filter to the executed program. This is a dangerous option that can result in leaking privileges to the container!!!")
    ret.add_argument("-C", "--allcaps", action="store_true", help="tell LXC not to drop capabilities. This is a dangerous option that can result in leaking privileges to the container!!!")
    ret.add_argument("-G", "--nocgroup", action="store_true", help="tell LXC not to switch to the container cgroup. This is a dangerous option that can result in leaking privileges to the container!!!")
    ret.add_argument('COMMAND', nargs='*', help="command to run")
    return ret

def arguments_logcat(subparser):
    ret = subparser.add_parser("logcat", help="show android logcat")
    return ret

def arguments_adb(subparser):
    ret = subparser.add_parser("adb", help="manage adb connection")
    sub = ret.add_subparsers(title="subaction", dest="subaction")
    sub.add_parser("connect", help="connect adb to the Android container")
    sub.add_parser("disconnect", help="disconnect adb from the Android container")
    return ret

def arguments():
    parser = argparse.ArgumentParser(prog="waydroid")

    # Other
    parser.add_argument("-V", "--version", action="version",
                        version=tools.config.version)

    # Logging
    parser.add_argument("-l", "--log", dest="log", default=None,
                        help="path to log file")
    parser.add_argument("--details-to-stdout", dest="details_to_stdout",
                        help="print details (e.g. build output) to stdout,"
                             " instead of writing to the log",
                        action="store_true")
    parser.add_argument("-v", "--verbose", dest="verbose",
                        action="store_true", help="write even more to the"
                        " logfiles (this may reduce performance)")
    parser.add_argument("-q", "--quiet", dest="quiet", action="store_true",
                        help="do not output any log messages")
    parser.add_argument("-w", "--wait", dest="wait_for_init", action="store_true",
                        help="wait for init before running")

    # Actions
    sub = parser.add_subparsers(title="action", dest="action")

    arguments_status(sub)
    arguments_log(sub)
    arguments_init(sub)
    arguments_upgrade(sub)
    arguments_session(sub)
    arguments_container(sub)
    arguments_app(sub)
    arguments_prop(sub)
    arguments_fullUI(sub)
    arguments_firstLaunch(sub)
    arguments_shell(sub)
    arguments_logcat(sub)
    arguments_adb(sub)

    if argcomplete:
        argcomplete.autocomplete(parser, always_complete_options="long")

    # Parse and extend arguments (also backup unmodified result from argparse)
    args = parser.parse_args()
    return args
