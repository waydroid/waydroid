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
open_notifications = {}
action_handlers = {}

def stop_main_loop():
    if main_loop:
        main_loop.quit()

    return False

def get_app_name(package_name):
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

    platform_service = IPlatform.get_service(args)
    if platform_service:
        apps_list = platform_service.getAppsInfo()
        app_name_dict = {app['packageName']: app['name'] for app in apps_list}
        app_name = app_name_dict.get(package_name)
        return True, app_name

    logging.error("Failed to access IPlatform service")

    if session["state"] == "FROZEN":
        cm.Freeze()

    return False, None

### Notification click actions ###

def on_action_invoked(notification_id, action_key):
    if notification_id in action_handlers:
        handler = action_handlers[notification_id]
        handler(action_key)
        del action_handlers[notification_id]

def create_action_handler(pkg_name):
    def handler(action_key):
        if action_key == 'open':
            args = helpers.arguments()
            args.cache = {}
            args.work = config.defaults["work"]
            args.config = args.work + "/waydroid.cfg"
            args.log = args.work + "/waydroid.log"
            args.sudo_timer = True
            args.timeout = 1800
            args.PACKAGE = pkg_name
            app_manager.launch(args)
    return handler

### Calls to freedesktop notification API ###

def notify_send(app_name, package_name, ticker, title, text, _is_foreground_service,
                show_light, updates_id):
    notification_id = 0

    # When the title and text fields are not present, we choose an empty title
    # and the ticker as text.
    if title == '' or text == '':
        title = ''
        text = ticker

    bus = dbus.SessionBus()
    notification_service = bus.get_object('org.freedesktop.Notifications',
                                          '/org/freedesktop/Notifications')
    notifications = dbus.Interface(notification_service,
                                   dbus_interface='org.freedesktop.Notifications')
    notifications.connect_to_signal("ActionInvoked", on_action_invoked)

    notification_id = notifications.Notify(
        app_name,
        updates_id,
        config.session_defaults["waydroid_data"] + "/icons/"
        + package_name + ".png",
        title,
        text,
        ['default', 'Open', 'open', 'Open'],
        {'urgency': 1 if show_light else 0},
        5000
    )

    action_handlers[int(notification_id)] = create_action_handler(package_name)
    return notification_id

def close_notification_send(notification_id):
    bus = dbus.SessionBus()
    notification_service = bus.get_object('org.freedesktop.Notifications',
                                          '/org/freedesktop/Notifications')
    notifications = dbus.Interface(notification_service,
                                   dbus_interface='org.freedesktop.Notifications')

    notifications.CloseNotification(notification_id)

    if notification_id in action_handlers:
        del action_handlers[notification_id]

### Helper functions ###

def try_and_loop(f):
    global main_loop

    try:
        f()
    except dbus.DBusException:
        logging.error("WayDroid session is stopped")

    GLib.timeout_add_seconds(3, stop_main_loop)
    main_loop = GLib.MainLoop()
    main_loop.run()


### Callbacks for subscribed notification server signals ###

def on_new_message(msg_hash, _msg_id, package_name, ticker, title, text, is_foreground_service,
                   is_group_summary, show_light, _when):
    #logging.info(f"Received new message notification: {msg_hash}, {_msg_id}, {package_name}, " +
    #             f"{ticker}, {title}, {text}, {is_foreground_service}, {is_group_summary}, " +
    #             f"{show_light}, {_when}")
    def fun():
        ok, app_name = get_app_name(package_name)
        if ok and not is_group_summary:
            notification_id = notify_send(app_name, package_name, ticker, title, text,
                                          is_foreground_service, show_light, 0)
            open_notifications[msg_hash] = notification_id

    try_and_loop(fun)

def on_update_message(msg_hash, replaces_hash, _msg_id, package_name, ticker, title, text,
                      is_foreground_service, _is_group_summary, show_light, _when):
    #logging.info(f"Received update message notification: {msg_hash}, {replaces_hash}, " +
    #             f"{_msg_id}, {package_name}, {ticker}, {title}, {text}, " +
    #             f"{is_foreground_service}, {_is_group_summary}, {show_light}, {_when}")
    def fun():
        ok, app_name = get_app_name(package_name)
        if ok and replaces_hash in open_notifications:
            notification_id = notify_send(app_name, package_name, ticker, title, text,
                                          is_foreground_service, show_light,
                                          open_notifications[replaces_hash])
            open_notifications[msg_hash] = notification_id
            del open_notifications[replaces_hash]

    try_and_loop(fun)

# on android, a notification disappeared (and was not replaced by another)
def on_delete_message(msg_hash):
    #logging.info(f"Received delete message notification: {msg_hash}")
    def fun():
        if msg_hash in open_notifications:
            close_notification_send(open_notifications[msg_hash])
            del open_notifications[msg_hash]

    try_and_loop(fun)

def start(_args):
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
    system_bus.add_signal_receiver(
        on_update_message,
        signal_name="UpdateMessage",
        dbus_interface='id.waydro.Notification',
        bus_name='id.waydro.Notification',
        path='/id/waydro/Notification'
    )
    system_bus.add_signal_receiver(
        on_delete_message,
        signal_name="DeleteMessage",
        dbus_interface='id.waydro.Notification',
        bus_name='id.waydro.Notification',
        path='/id/waydro/Notification'
    )

    main_loop = GLib.MainLoop()
    main_loop.run()

def stop(_args):
    global main_loop
    if main_loop is None:
        logging.info("Notification client service is not running.")
        return

    main_loop.quit()
    main_loop = None
