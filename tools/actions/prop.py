import logging
import tools.helpers.props
import tools.helpers.ipc
import dbus

def get(args):
    try:
        tools.helpers.ipc.DBusSessionService()

        cm = tools.helpers.ipc.DBusContainerService()
        session = cm.GetSession()
        if session["state"] == "FROZEN":
            cm.Unfreeze()

        ret = tools.helpers.props.get(args, args.key)
        if ret:
            print(ret)

        if session["state"] == "FROZEN":
            cm.Freeze()
    except (dbus.DBusException, KeyError):
        logging.error("WayDroid session is stopped")

def set(args):
    try:
        tools.helpers.ipc.DBusSessionService()

        cm = tools.helpers.ipc.DBusContainerService()
        session = cm.GetSession()
        if session["state"] == "FROZEN":
            cm.Unfreeze()

        tools.helpers.props.set(args, args.key, args.value)

        if session["state"] == "FROZEN":
            cm.Freeze()
    except (dbus.DBusException, KeyError):
        logging.error("WayDroid session is stopped")
