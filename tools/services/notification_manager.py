# Copyright 2025 Alessandro Astone
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import threading
import tools.config
from tools.interfaces import INotifications
from gi.repository import GLib
import dbus

stopping = False
bus_signals = []

def start(args, session):
    waydroid_data = session["waydroid_data"]

    def onListenerDeath(listener):
        listeners.remove(listener)

    def registerListener(listener):
        listener.addDeathHandler(onListenerDeath)
        listeners.append(listener)

    def notify(replaces_id, app_name, package_name, summary, body, actions, image_data, category, suppress_sound, expire_timeout, resident, transient, urgency):
        # By reading the spec, I believe app_icon should be pointing to the desktop entry Icon=
        # but when we set it plasmashell uses it in place of image-data.
        # Ignore app_icon and use desktop-entry to show the app icon.
        # app_icon = f"file://{waydroid_data}/icons/{package_name}.png"
        app_icon = ""
        actions_flat = [s for action in actions for s in (action.id, action.label)]
        hints = {
            "desktop-entry": f"waydroid.{package_name}",
            "resident": dbus.types.Boolean(resident),
            "transient": dbus.types.Boolean(transient),
            "urgency": dbus.types.Byte(urgency),
            "suppress-sound": dbus.types.Boolean(suppress_sound),
        }
        if category:
            hints["category"] = category
        if image_data:
            hints["image-data"] = dbus.types.Struct([
                image_data.width,
                image_data.height,
                image_data.rowstride,
                image_data.has_alpha,
                8,
                4 if image_data.has_alpha else 3,
                dbus.types.Array(image_data.data, signature = "y")
            ])
        try:
            return dbus_proxy.Notify(app_name, replaces_id, app_icon, summary, body, actions_flat, hints, expire_timeout)
        except dbus.DBusException as e:
            logging.warning(f"Failed to post notification: {e}")
            return INotifications.ID_NONE

    def closeNotification(notification_id):
        try:
            dbus_proxy.CloseNotification(notification_id)
        except dbus.DBusException as e:
            logging.warning(f"Failed to close notification: {e}")

    def onActivationToken(notification_id, token):
        pending_tokens[int(notification_id)] = str(token)

    def onActionInvoked(notification_id, action_id):
        token = pending_tokens.pop(int(notification_id))
        for listener in listeners:
            listener.onActionInvoked(int(notification_id), str(action_id), str(token))

    def service_thread():
        while not stopping:
            INotifications.add_service(args, registerListener, notify, closeNotification)

    try:
        dbus_proxy = dbus.Interface(dbus.SessionBus().get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications"),
                                    "org.freedesktop.Notifications")
    except dbus.DBusException as e:
        logging.info("Skipping notification manager service because we could not connect to the notifications server: %s", str(e))
        return

    listeners = []
    pending_tokens = dict()
    bus_signals.append(dbus_proxy.connect_to_signal("ActivationToken", onActivationToken))
    bus_signals.append(dbus_proxy.connect_to_signal("ActionInvoked", onActionInvoked))

    global stopping
    stopping = False
    args.notification_manager = threading.Thread(target=service_thread)
    args.notification_manager.start()

def stop(args):
    global stopping
    stopping = True
    for signal in bus_signals:
        signal.remove()
    try:
        if args.notificationLoop:
            args.notificationLoop.quit()
    except AttributeError:
        logging.debug("NotificationManager service is not even started")
