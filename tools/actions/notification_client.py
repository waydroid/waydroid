# Copyright 2023 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
from tools import helpers
from tools import config
from tools.helpers import ipc
from tools.interfaces import IPlatform
from tools.actions import app_manager

main_loop = None

def stop_main_loop():
    global main_loop
    if main_loop:
        main_loop.quit()

    return False

def on_action_invoked(notification, action_key):
    args = None
    if action_key == 'open':
        args = helpers.arguments()
        args.cache = {}
        args.work = config.defaults["work"]
        args.config = args.work + "/waydroid.cfg"
        args.log = args.work + "/waydroid.log"
        args.sudo_timer = True
        args.timeout = 1800
        app_manager.showFullUI(args)

def on_new_message(package_name, count):
    # logging.info(f"Received new message notification: packagename = {package_name}, count = {count}")

    args = None
    app_name_dict = {}
    try:
        args = helpers.arguments()
        args.cache = {}
        args.work = config.defaults["work"]
        args.config = args.work + "/waydroid.cfg"
        args.log = args.work + "/waydroid.log"
        args.sudo_timer = True
        args.timeout = 1800

        ipc.DBusSessionService()
        cm = ipc.DBusContainerService()
        session = cm.GetSession()
        if session["state"] == "FROZEN":
            cm.Unfreeze()

        platformService = IPlatform.get_service(args)
        if platformService:
            appsList = platformService.getAppsInfo()
            app_name_dict = {app['packageName']: app['name'] for app in appsList}
            app_name = app_name_dict.get(package_name)
            notify_send(app_name, count)
        else:
            logging.error("Failed to access IPlatform service")

        if session["state"] == "FROZEN":
            cm.Freeze()

    except dbus.DBusException:
        logging.error("WayDroid session is stopped")

def notify_send(app_name, count):
    global main_loop

    bus = dbus.SessionBus()
    notification_service = bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
    notifications = dbus.Interface(notification_service, dbus_interface='org.freedesktop.Notifications')
    notifications.connect_to_signal("ActionInvoked", on_action_invoked)

    notifications.Notify(
        app_name,
        0,
        "/usr/share/icons/hicolor/512x512/apps/waydroid.png",
        f"{app_name}",
        f"You have {count} notification(s)",
        ['default', 'Open', 'open', 'Open'],
        {'urgency': 1},
        5000
    )

    GLib.timeout_add_seconds(3, stop_main_loop)
    main_loop = GLib.MainLoop()
    main_loop.run()

def start(args):
    global main_loop
    if main_loop is not None:
        logging.info("Notification client is already running.")
        return

    logging.info("Starting notification client service")

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    system_bus = dbus.SystemBus()
    system_bus.add_signal_receiver(
        on_new_message,
        signal_name="NewMessage",
        dbus_interface='id.waydro.Notification',
        bus_name='id.waydro.Notification',
        path='/id/waydro/Notification'
    )

    main_loop = GLib.MainLoop()
    main_loop.run()

def stop(args):
    global main_loop
    if main_loop is None:
        logging.info("Notification client service is not running.")
        return

    main_loop.quit()
    main_loop = None
