# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import sys
import logging
import os
import traceback

from . import actions
from . import config
from . import helpers
from .helpers import logging as tools_logging


def main():
    def actionNeedRoot(action):
        if os.geteuid() != 0:
            raise RuntimeError(
                "Action \"{}\" needs root access".format(action))

    # Wrap everything to display nice error messages
    args = None
    try:
        os.umask(0o000)
        # Parse arguments, set up logging
        args = helpers.arguments()
        args.cache = {}
        args.work = config.defaults["work"]
        args.config = args.work + "/waydroid.cfg"
        args.log = args.work + "/tools.log"
        args.sudo_timer = True
        args.timeout = 1800

        if not os.path.isfile(args.config):
            if args.action and args.action != "init":
                print('ERROR: WayDroid is not initialized, run "waydroid init"')
                return 0
            elif os.geteuid() == 0 and args.action == "init":
                os.mkdir(args.work)
            else:
                args.log = "/tmp/tools.log"

        tools_logging.init(args)

        # Initialize or require config
        if args.action == "init":
            actionNeedRoot(args.action)
            actions.init(args)
        elif args.action == "upgrade":
            actionNeedRoot(args.action)
            actions.upgrade(args)
        elif args.action == "session":
            if args.subaction == "start":
                actions.session_manager.start(args)
            elif args.subaction == "stop":
                actions.session_manager.stop(args)
            else:
                logging.info(
                    "Run waydroid {} -h for usage information.".format(args.action))
        elif args.action == "container":
            actionNeedRoot(args.action)
            if args.subaction == "start":
                actions.container_manager.start(args)
            elif args.subaction == "stop":
                actions.container_manager.stop(args)
            elif args.subaction == "freeze":
                actions.container_manager.freeze(args)
            elif args.subaction == "unfreeze":
                actions.container_manager.unfreeze(args)
            else:
                logging.info(
                    "Run waydroid {} -h for usage information.".format(args.action))
        elif args.action == "app":
            if args.subaction == "install":
                actions.app_manager.install(args)
            elif args.subaction == "remove":
                actions.app_manager.remove(args)
            elif args.subaction == "launch":
                actions.app_manager.launch(args)
            elif args.subaction == "list":
                actions.app_manager.list(args)
            else:
                logging.info(
                    "Run waydroid {} -h for usage information.".format(args.action))
        elif args.action == "prop":
            if args.subaction == "get":
                ret = helpers.props.get(args, args.key)
                if ret:
                    print(ret)
            elif args.subaction == "set":
                helpers.props.set(args, args.key, args.value)
            else:
                logging.info(
                    "Run waydroid {} -h for usage information.".format(args.action))
        elif args.action == "shell":
            actionNeedRoot(args.action)
            helpers.lxc.shell(args)
        elif args.action == "logcat":
            actionNeedRoot(args.action)
            helpers.lxc.logcat(args)
        elif args.action == "show-full-ui":
            actions.app_manager.showFullUI(args)
        elif args.action == "status":
            actions.status.print_status(args)
        elif args.action == "log":
            if args.clear_log:
                helpers.run.user(args, ["truncate", "-s", "0", args.log])
            helpers.run.user(
                args, ["tail", "-n", args.lines, "-F", args.log], output="tui")
        else:
            logging.info("Run waydroid -h for usage information.")

        #logging.info("Done")

    except Exception as e:
        # Dump log to stdout when args (and therefore logging) init failed
        if not args:
            logging.getLogger().setLevel(logging.DEBUG)

        logging.info("ERROR: " + str(e))
        logging.info("See also: <https://github.com/waydroid>")
        logging.debug(traceback.format_exc())

        # Hints about the log file (print to stdout only)
        log_hint = "Run 'waydroid log' for details."
        if not args or not os.path.exists(args.log):
            log_hint += (" Alternatively you can use '--details-to-stdout' to"
                         " get more output, e.g. 'waydroid"
                         " --details-to-stdout init'.")
        print(log_hint)
        return 1


if __name__ == "__main__":
    sys.exit(main())
