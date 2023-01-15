# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import time
import signal
import sys
import shutil
import tools.config
import tools.helpers.ipc
from tools import services
import dbus
import dbus.service
import dbus.exceptions
from gi.repository import GLib
import copy

class DbusSessionManager(dbus.service.Object):
    def __init__(self, looper, bus, object_path, args):
        self.args = args
        self.looper = looper
        dbus.service.Object.__init__(self, bus, object_path)

    @dbus.service.method("id.waydro.SessionManager", in_signature='', out_signature='')
    def Stop(self):
        do_stop(self.args, self.looper)
        stop_container()

def service(args, looper):
    dbus_obj = DbusSessionManager(looper, dbus.SessionBus(), '/SessionManager', args)
    looper.run()

def start(args, unlocked_cb=None):
    try:
        name = dbus.service.BusName("id.waydro.Session", dbus.SessionBus(), do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        logging.error("Session is already running")
        if unlocked_cb:
            unlocked_cb()
        return

    session = copy.copy(tools.config.session_defaults);
    wayland_display = session["wayland_display"]
    if wayland_display == "None" or not wayland_display:
        logging.warning('WAYLAND_DISPLAY is not set, defaulting to "wayland-0"')
    waydroid_data = session["waydroid_data"]
    if not os.path.isdir(waydroid_data):
        os.makedirs(waydroid_data)
    dpi = tools.helpers.props.host_get(args, "ro.sf.lcd_density")
    if dpi == "":
        dpi = os.getenv("GRID_UNIT_PX")
        if dpi is not None:
            dpi = str(int(dpi) * 20)
        else:
            dpi = "0"
    session["lcd_density"] = dpi

    mainloop = GLib.MainLoop()

    def sigint_handler(data):
        do_stop(args, mainloop)
        stop_container()

    def sigusr_handler(data):
        do_stop(args, mainloop)

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, sigint_handler, None)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, sigint_handler, None)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, sigusr_handler, None)
    try:
        tools.helpers.ipc.DBusContainerService().Start(session)
    except dbus.DBusException as e:
        if e.get_dbus_name().startswith("org.freedesktop.DBus.Python"):
            logging.error(e.get_dbus_message().splitlines()[-1])
        else:
            logging.error("WayDroid container is not listening")
        sys.exit(0)

    services.user_manager.start(args, session, unlocked_cb)
    services.clipboard_manager.start(args)
    service(args, mainloop)

def do_stop(args, looper):
    services.user_manager.stop(args)
    services.clipboard_manager.stop(args)
    looper.quit()

def stop(args):
    try:
        tools.helpers.ipc.DBusSessionService().Stop()
    except dbus.DBusException:
        stop_container()

def stop_container():
    try:
        tools.helpers.ipc.DBusContainerService().Stop()
    except dbus.DBusException:
        pass
