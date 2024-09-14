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
from tools.interfaces import IPlatform
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
        stop_container(quit_session=False)

    @dbus.service.method("id.waydro.SessionManager", in_signature='', out_signature='s')
    def VendorType(self):
        cfg = tools.config.load(self.args)
        return cfg["waydroid"]["vendor_type"]

    @dbus.service.method("id.waydro.SessionManager", in_signature='', out_signature='s')
    def IpAddress(self):
        ip_address = tools.helpers.net.get_device_ip_address()
        return ip_address if ip_address else "UNKNOWN"

    @dbus.service.method("id.waydro.SessionManager", in_signature='', out_signature='s')
    def LineageVersion(self):
        full_version = tools.helpers.props.get(self.args, "ro.lineage.display.version")
        version_parts = full_version.split('-')
        version = '-'.join(version_parts[:2])
        return version

    @dbus.service.method("id.waydro.SessionManager", in_signature='s', out_signature='')
    def RemoveApp(self, packageName):
        tools.helpers.ipc.DBusContainerService().RemoveApp(packageName)

    @dbus.service.method("id.waydro.SessionManager", in_signature='s', out_signature='')
    def InstallApp(self, packagePath):
        prop_file_path = '/var/lib/waydroid/waydroid.prop'
        waydroid_host_data_path = None
        with open(prop_file_path, 'r') as file:
            for line in file:
                if line.startswith('waydroid.host_data_path'):
                    key, value = line.split('=', 1)
                    waydroid_host_data_path = value.strip()
                    break

        if waydroid_host_data_path is None:
            return

        tmp_dir = waydroid_host_data_path + "/waydroid_tmp"
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        shutil.copyfile(packagePath, tmp_dir + "/base.apk")
        tools.helpers.ipc.DBusContainerService().InstallBaseApk()
        os.remove(tmp_dir + "/base.apk")

    @dbus.service.method("id.waydro.SessionManager", in_signature='s', out_signature='s')
    def NameToPackageName(self, appName):
        platformService = IPlatform.get_service(self.args)
        if platformService:
            appsList = platformService.getAppsInfo()
            for app in appsList:
                if appName == app["name"]:
                    return app["packageName"]
        return ""

    @dbus.service.method("id.waydro.SessionManager", in_signature='s', out_signature='s')
    def PackageNameToName(self, packageName):
        platformService = IPlatform.get_service(self.args)
        if platformService:
            appsList = platformService.getAppsInfo()
            for app in appsList:
                if packageName == app["packageName"]:
                    return app["name"]
        return ""

def service(args, looper):
    dbus_obj = DbusSessionManager(looper, dbus.SessionBus(), '/SessionManager', args)
    looper.run()

def start(args, unlocked_cb=None, background=True):
    try:
        name = dbus.service.BusName("id.waydro.Session", dbus.SessionBus(), do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        logging.error("Session is already running")
        if unlocked_cb:
            unlocked_cb()
        return

    session = copy.copy(tools.config.session_defaults)

    # TODO: also support WAYLAND_SOCKET?
    wayland_display = session["wayland_display"]
    if wayland_display == "None" or not wayland_display:
        logging.warning('WAYLAND_DISPLAY is not set, defaulting to "wayland-0"')
        wayland_display = session["wayland_display"] = "wayland-0"

    if os.path.isabs(wayland_display):
        wayland_socket_path = wayland_display
    else:
        xdg_runtime_dir = session["xdg_runtime_dir"]
        if xdg_runtime_dir == "None" or not xdg_runtime_dir:
            logging.error(f"XDG_RUNTIME_DIR is not set; please don't start a Waydroid session with 'sudo'!")
            sys.exit(1)
        wayland_socket_path = os.path.join(xdg_runtime_dir, wayland_display)
    if not os.path.exists(wayland_socket_path):
        logging.error(f"Wayland socket '{wayland_socket_path}' doesn't exist; are you running a Wayland compositor?")
        sys.exit(1)

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

    session["background_start"] = "true"

    mainloop = GLib.MainLoop()

    def sigint_handler(data):
        do_stop(args, mainloop)
        stop_container(quit_session=False)

    def sigusr_handler(data):
        do_stop(args, mainloop)

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, sigint_handler, None)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, sigint_handler, None)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, sigusr_handler, None)
    try:
        tools.helpers.ipc.DBusContainerService().Start(session)
    except dbus.DBusException as e:
        logging.debug(e)
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
        stop_container(quit_session=True)

def stop_container(quit_session):
    try:
        tools.helpers.ipc.DBusContainerService().Stop(quit_session)
    except dbus.DBusException:
        pass
