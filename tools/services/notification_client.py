# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import dbus
import dbus.service
import dbus.mainloop.glib
import threading
from gi.repository import GLib
from tools import helpers
from tools import config
from tools.helpers import ipc
from tools.interfaces import IPlatform
from tools.actions import app_manager

stopping = False

class NotificationService:
    def __init__(self, args):
        self.args = args
        self.open_notifications = {}
        self.action_handlers = {}

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.setup_dbus_signals()

    def setup_dbus_signals(self):
        try:
            system_bus = dbus.SystemBus()
            system_bus.add_signal_receiver(
                self.on_new_message,
                signal_name="NewMessage",
                dbus_interface='id.waydro.Notification',
                bus_name='id.waydro.Notification',
                path='/id/waydro/Notification'
            )
            system_bus.add_signal_receiver(
                self.on_update_message,
                signal_name="UpdateMessage",
                dbus_interface='id.waydro.Notification',
                bus_name='id.waydro.Notification',
                path='/id/waydro/Notification'
            )
            system_bus.add_signal_receiver(
                self.on_delete_message,
                signal_name="DeleteMessage",
                dbus_interface='id.waydro.Notification',
                bus_name='id.waydro.Notification',
                path='/id/waydro/Notification'
            )
        except Exception as e:
            logging.error(f"Failed to setup DBus signals: {e}")

    def get_app_name(self, package_name):
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

    def on_action_invoked(self, notification_id, action_key):
        if notification_id in self.action_handlers:
            handler = self.action_handlers[notification_id]
            handler(action_key)
            del self.action_handlers[notification_id]

    def create_action_handler(self, pkg_name):
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

    def notify_send(self, app_name, package_name, ticker, title, text, is_foreground_service,
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
        notifications.connect_to_signal("ActionInvoked", self.on_action_invoked)

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

        self.action_handlers[int(notification_id)] = self.create_action_handler(package_name)
        return notification_id

    def close_notification_send(self, notification_id):
        bus = dbus.SessionBus()
        notification_service = bus.get_object('org.freedesktop.Notifications',
                                            '/org/freedesktop/Notifications')
        notifications = dbus.Interface(notification_service,
                                    dbus_interface='org.freedesktop.Notifications')

        notifications.CloseNotification(notification_id)

        if notification_id in self.action_handlers:
            del self.action_handlers[notification_id]

    ### Callbacks for subscribed notification server signals ###

    def on_new_message(self, msg_hash, _msg_id, package_name, ticker, title, text, is_foreground_service,
                       is_group_summary, show_light, _when):
        logging.debug(f"Received new message notification: {msg_hash}, {_msg_id}, {package_name}, " +
                     f"{ticker}, {title}, {text}, {is_foreground_service}, {is_group_summary}, " +
                     f"{show_light}, {_when}")
        try:
            ok, app_name = self.get_app_name(package_name)
            if ok and not is_group_summary:
                notification_id = self.notify_send(app_name, package_name, ticker, title, text,
                                            is_foreground_service, show_light, 0)
                self.open_notifications[msg_hash] = notification_id
        except dbus.DBusException:
            logging.error("WayDroid session is stopped")

    def on_update_message(self, msg_hash, replaces_hash, _msg_id, package_name, ticker, title, text,
                          is_foreground_service, _is_group_summary, show_light, _when):
        logging.debug(f"Received update message notification: {msg_hash}, {replaces_hash}, " +
                     f"{_msg_id}, {package_name}, {ticker}, {title}, {text}, " +
                     f"{is_foreground_service}, {_is_group_summary}, {show_light}, {_when}")
        try:
            ok, app_name = self.get_app_name(package_name)
            if ok and replaces_hash in self.open_notifications:
                notification_id = self.notify_send(app_name, package_name, ticker, title, text,
                                            is_foreground_service, show_light,
                                            self.open_notifications[replaces_hash])
                self.open_notifications[msg_hash] = notification_id
                del self.open_notifications[replaces_hash]
        except dbus.DBusException:
            logging.error("WayDroid session is stopped")

    # on android, a notification disappeared (and was not replaced by another)
    def on_delete_message(self, msg_hash):
        logging.debug(f"Received delete message notification: {msg_hash}")
        try:
            if msg_hash in self.open_notifications:
                self.close_notification_send(self.open_notifications[msg_hash])
                del self.open_notifications[msg_hash]
        except dbus.DBusException:
            logging.error("WayDroid session is stopped")

    def run(self):
        self.args.notificationLoop = GLib.MainLoop()
        logging.debug("Notification client service running")
        self.args.notificationLoop.run()

def service_thread(args):
    global stopping

    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        notification_service = NotificationService(args)

        while not stopping:
            try:
                notification_service.run()
            except Exception as e:
                logging.error(f"Error in notification service loop: {e}")
                if not stopping:
                    continue
                break
    except Exception as e:
        logging.error(f"Notification service error: {str(e)}")

def start(args):
    global stopping
    logging.debug("Starting notification client service")

    stopping = False
    args.notification_manager = threading.Thread(target=service_thread, args=(args,))
    args.notification_manager.daemon = True
    args.notification_manager.start()

def stop(args):
    global stopping

    logging.debug("Stopping notification client service")
    stopping = True

    try:
        if hasattr(args, 'notificationLoop') and args.notificationLoop:
            args.notificationLoop.quit()
    except Exception as e:
        logging.error(f"Error stopping notification service: {e}")
