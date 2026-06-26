# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import sys
import logging
import os
import traceback
from argparse import Namespace

import dbus.mainloop.glib
import dbus
import dbus.exceptions

from . import actions
from . import config
from . import helpers
from .helpers import logging as tools_logging


def prep_args(args:Namespace):
    args.cache = {}
    args.work = config.defaults["work"]
    args.config = args.work + "/waydroid.cfg"
    args.log = args.work + "/waydroid.log"
    args.sudo_timer = True
    args.timeout = 1800


def main():
    def action_need_root(action):
        if os.geteuid() != 0:
            raise RuntimeError(
                f"Action '{action}' needs root access")

    # Wrap everything to display nice error messages
    args: Namespace = Namespace()
    try:
        # Parse arguments, set up logging
        args = helpers.arguments()
        prep_args(args)

        if os.geteuid() == 0:
            if not os.path.exists(args.work):
                os.mkdir(args.work)
        elif not os.path.exists(args.log):
            args.log = "/tmp/tools.log"

        tools_logging.init(args)

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        dbus.mainloop.glib.threads_init()

        if args.action is None:
            args.action = "first-launch"

        if not actions.initializer.is_initialized(args) and \
                args.action not in ("init", "container", "first-launch", "log", "bugreport"):
            print('Waydroid is not initialized, run "waydroid init"')
            return 0

        if args.action == "init":
            if args.client:
                actions.remote_init_client(args)
            else:
                action_need_root(args.action)
                actions.init(args)
        elif args.action == "upgrade":
            action_need_root(args.action)
            actions.upgrade(args)
        elif args.action == "session":
            if args.subaction == "start":
                actions.session_manager.start(args)
            elif args.subaction == "stop":
                actions.session_manager.stop(args)
            else:
                logging.info(
                    f"Run waydroid {args.action} -h for usage information.")
        elif args.action == "container":
            action_need_root(args.action)
            if args.subaction in ['start', 'stop', "restart", 'freeze', 'unfreeze']:
                getattr(actions.container_manager, args.subaction)(args)
            else:
                logging.info(
                    f"Run waydroid {args.action} -h for usage information.")
        elif args.action == "app":
            if args.subaction in ["install", "remove", "launch", "intent", "list"]:
                getattr(actions.app_manager, args.subaction)(args)
            else:
                logging.info(
                    f"Run waydroid {args.action} -h for usage information.")
        elif args.action == "prop":
            if args.subaction == "get":
                actions.prop.get(args)
            elif args.subaction == "set":
                actions.prop.set(args)
            else:
                logging.info(
                    f"Run waydroid {args.action} -h for usage information.")
        elif args.action == "shell":
            action_need_root(args.action)
            helpers.lxc.shell(args)
        elif args.action == "logcat":
            action_need_root(args.action)
            helpers.lxc.logcat(args)
        elif args.action == "show-full-ui":
            actions.app_manager.showFullUI(args)
        elif args.action == "first-launch":
            if not actions.initializer.is_initialized(args):
                actions.remote_init_client(args)
            if actions.initializer.is_initialized(args):
                actions.app_manager.showFullUI(args)
        elif args.action == "status":
            actions.status.print_status(args)
        elif args.action == "adb":
            if args.subaction == "connect":
                helpers.net.adb_connect(args)
            elif args.subaction == "disconnect":
                helpers.net.adb_disconnect(args)
            else:
                logging.info(f"Run waydroid {args.action} -h for usage information.")
        elif args.action == "log":
            if args.clear_log:
                helpers.run.user(args, ["truncate", "-s", "0", args.log])
            try:
                helpers.run.user(
                    args, ["tail", "-n", args.lines, "-F", args.log], output="tui")
            except KeyboardInterrupt:
                pass
        elif args.action == "bugreport":
            actions.bugreport(args)
        else:
            logging.info("Run waydroid -h for usage information.")

        #logging.info("Done")

    except Exception as e:
        # Dump log to stdout when args (and therefore logging) init failed
        if not args:
            logging.getLogger().setLevel(logging.DEBUG)

        logging.info(f"ERROR: {e}")
        logging.info("See also: <https://github.com/waydroid>")
        logging.debug(traceback.format_exc())

        if args and args.details_to_stdout:
            return 1

        # Hints about the log file (print to stdout only)
        log_hint = "Run 'waydroid log' for details."
        if not args or not os.path.exists(args.log) or not args.action == "container":
            log_hint = ("Use '--details-to-stdout' to get more details:\n"
                        f"  {sys.argv[0]} --details-to-stdout {' '.join(sys.argv[1:])}")
        print(log_hint)
        return 1


if __name__ == "__main__":
    sys.exit(main())
