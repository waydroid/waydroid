# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import sys
import logging
import os
import traceback
import dbus.mainloop.glib
import dbus
import dbus.exceptions

from . import actions
from . import config
from . import helpers
from .helpers import logging as tools_logging

# ROOT_ACTIONS and ALLOWED_UNINITIALIZED are derived from the guard flags
# declared on each DISPATCH entry below, so a new action declares its guards
# in the one place it is added.

def prep_args(args):
    args.cache = {}
    args.work = config.defaults["work"]
    args.config = args.work + "/waydroid.cfg"
    args.log = args.work + "/waydroid.log"
    args.sudo_timer = True
    args.timeout = 1800

def _action_need_root(action):
    if os.geteuid() != 0:
        raise RuntimeError(
            "Action \"{}\" needs root access".format(action))

def _log_path(args):
    """
    Choose the log file that `waydroid log` should follow.

    Non-root users prefer the root container log (where container service
    errors land) when it is readable, unless an explicit -l/--log was given.
    """
    if os.geteuid() != 0 and not args.user_log:
        root_log = config.defaults["work"] + "/waydroid.log"
        if os.access(root_log, os.R_OK):
            return root_log
    return args.log

def _log(args):
    """Follow the log file, preferring the root container log as a user."""
    log_path = _log_path(args)
    if args.clear_log:
        helpers.run.user(args, ["truncate", "-s", "0", args.log])
    try:
        helpers.run.user(
            args, ["tail", "-n", args.lines, "-F", log_path], output="tui")
    except KeyboardInterrupt:
        pass

def _first_launch(args):
    if not actions.initializer.is_initialized(args):
        actions.remote_init_client(args)
    if actions.initializer.is_initialized(args):
        actions.app_manager.showFullUI(args)

def _init(args):
    if args.client:
        actions.remote_init_client(args)
    else:
        _action_need_root("init")
        actions.init(args)

class _ActionEntry(dict):
    """A DISPATCH entry: {subaction or None: handler} plus guard flags.

    Subclassing dict keeps lookups (``table.get(subaction)``, ``None in
    table``) unchanged; the flags declare how the action is gated in main()
    and are what ROOT_ACTIONS / ALLOWED_UNINITIALIZED are derived from.
    """


def _entry(handlers, *, root=False, uninitialized=False):
    """Build a DISPATCH entry, marking the action's guard flags."""
    entry = _ActionEntry(handlers)
    entry.need_root = root
    entry.allowed_uninitialized = uninitialized
    return entry


# Action dispatch table: action -> entry mapping {subaction or None: handler}
# plus guard flags. Adding a new action or subaction requires only a new
# entry here; ROOT_ACTIONS and ALLOWED_UNINITIALIZED are derived from the
# flags below.
DISPATCH = {
    # "init" runs as a user for the --client variant; root is checked inside
    # _init instead of via the need_root flag.
    "init": _entry({None: _init}, uninitialized=True),
    "upgrade": _entry({None: actions.upgrade}, root=True),
    "session": _entry({"start": actions.session_manager.start,
                       "stop": actions.session_manager.stop}),
    "container": _entry({"start": actions.container_manager.start,
                         "stop": actions.container_manager.stop,
                         "restart": actions.container_manager.restart,
                         "freeze": actions.container_manager.freeze,
                         "unfreeze": actions.container_manager.unfreeze},
                        root=True, uninitialized=True),
    "app": _entry({"install": actions.app_manager.install,
                   "remove": actions.app_manager.remove,
                   "launch": actions.app_manager.launch,
                   "intent": actions.app_manager.intent,
                   "list": actions.app_manager.list}),
    "prop": _entry({"get": actions.prop.get,
                    "set": actions.prop.set}),
    "shell": _entry({None: helpers.lxc.shell}, root=True),
    "logcat": _entry({None: helpers.lxc.logcat}, root=True),
    "show-full-ui": _entry({None: actions.app_manager.showFullUI}),
    "first-launch": _entry({None: _first_launch}, uninitialized=True),
    "status": _entry({None: actions.status.print_status}),
    "adb": _entry({"connect": helpers.net.adb_connect,
                   "disconnect": helpers.net.adb_disconnect}),
    "log": _entry({None: _log}, uninitialized=True),
    "bugreport": _entry({None: actions.bugreport}, uninitialized=True),
}

# Actions that may run before waydroid is initialized, and actions that
# always require root. Derived from the DISPATCH flags so the two can't
# drift from the table. "init" is deliberately absent from ROOT_ACTIONS:
# its --client variant runs as a user and checks root itself in _init.
ALLOWED_UNINITIALIZED = frozenset(
    action for action, entry in DISPATCH.items()
    if entry.allowed_uninitialized)
ROOT_ACTIONS = frozenset(
    action for action, entry in DISPATCH.items() if entry.need_root)

def main():
    # Wrap everything to display nice error messages
    args = None
    try:
        # Parse arguments, set up logging
        args = helpers.arguments()
        user_log = args.log
        prep_args(args)

        if os.geteuid() == 0:
            if not os.path.exists(args.work):
                os.mkdir(args.work)
        elif not user_log and not os.path.exists(args.log):
            # Non-root users cannot write to the root work dir; fall back
            # to a per-user log unless an explicit -l/--log was given.
            args.log = "/tmp/tools.log"

        if user_log:
            args.log = user_log
        args.user_log = user_log

        tools_logging.init(args)

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        dbus.mainloop.glib.threads_init()

        if args.action is None:
            args.action = "first-launch"

        if not actions.initializer.is_initialized(args) and \
                args.action not in ALLOWED_UNINITIALIZED:
            print('Waydroid is not initialized, run "waydroid init"')
            return 0

        action_handlers = DISPATCH.get(args.action)
        if action_handlers is None:
            logging.info("Run waydroid -h for usage information.")
        else:
            if args.action in ROOT_ACTIONS:
                _action_need_root(args.action)
            handler = action_handlers.get(getattr(args, "subaction", None))
            if handler is None:
                logging.info(
                    "Run waydroid {} -h for usage information.".format(args.action))
            else:
                handler(args)

        #logging.info("Done")

    except KeyboardInterrupt:
        print("\nAborted.")
        return 1
    except Exception as e:
        # Dump log to stdout when args (and therefore logging) init failed
        if not args:
            logging.getLogger().setLevel(logging.DEBUG)

        logging.info("ERROR: " + str(e))
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
