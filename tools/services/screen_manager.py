# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import dbus
import dbus.service
import dbus.mainloop.glib
import threading
import time
from gi.repository import GLib
from tools import helpers

stopping = False

class ScreenService:
    def __init__(self, args):
        self.args = args
        self.session_id = None

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.session_id = self.get_session_id()
        logging.debug(f"Initial session ID: {self.session_id}")
        self.setup_dbus_signals()

    def setup_dbus_signals(self):
        try:
            if not self.session_id:
                logging.error("Cannot setup signals: No valid session ID")
                return

            session_path = f"/org/freedesktop/login1/session/{self.session_id}"
            system_bus = dbus.SystemBus()

            system_bus.add_signal_receiver(
                self.on_properties_changed,
                signal_name="PropertiesChanged",
                dbus_interface="org.freedesktop.DBus.Properties",
                bus_name="org.freedesktop.login1",
                path=session_path
            )

            logging.debug(f"Connected to session {self.session_id} for property changes")
        except Exception as e:
            logging.error(f"Failed to setup DBus signals: {e}")

    def update_session(self, new_session_id):
        if self.session_id:
            old_session_path = f"/org/freedesktop/login1/session/{self.session_id}"
            system_bus = dbus.SystemBus()

            system_bus.remove_signal_receiver(
                self.on_properties_changed,
                signal_name="PropertiesChanged",
                dbus_interface="org.freedesktop.DBus.Properties",
                bus_name="org.freedesktop.login1",
                path=old_session_path
            )

        self.session_id = new_session_id
        logging.debug(f"Updated session ID to: {self.session_id}")
        self.setup_dbus_signals()

    def get_session_id(self):
        try:
            system_bus = dbus.SystemBus()
            manager = system_bus.get_object("org.freedesktop.login1",
                                            "/org/freedesktop/login1",
                                            "org.freedesktop.login1.Manager")

            manager_interface = dbus.Interface(manager, "org.freedesktop.login1.Manager")
            sessions = manager_interface.ListSessionsEx()
            for session in sessions:
                session_id, uid, seat, display, vtnr, name, tty, remote, timestamp, obj_path = session
                if tty == "tty7":
                    logging.debug(f"Found tty7 session: {session_id}")
                    return session_id

            logging.warning("No tty7 session found")
        except dbus.exceptions.DBusException as e:
            logging.error(f"D-Bus error while getting session ID: {e}")
        except Exception as e:
            logging.error(f"Error getting session ID: {e}")

        return None

    def on_properties_changed(self, interface_name, changed_properties, invalidated_properties):
        if interface_name != "org.freedesktop.login1.Session":
            return

        if "Active" in changed_properties:
            active = bool(changed_properties["Active"])
            logging.debug(f"Session active state changed: {active}")

            if not active:
                logging.debug("Session became inactive, searching for new active session...")

                new_session_id = self.get_session_id()
                while new_session_id == self.session_id:
                    logging.debug("Got the same session ID, waiting before retrying...")
                    new_session_id = self.get_session_id()

                if new_session_id:
                    logging.debug(f"Found new session: {new_session_id}, updating listener...")
                    self.update_session(new_session_id)

        if "IdleHint" in changed_properties:
            idle_hint = bool(changed_properties["IdleHint"])
            logging.info(f"IdleHint changed: {idle_hint}")

            cm = helpers.ipc.DBusContainerService()
            session = cm.GetSession()
            if session["state"] == "FROZEN":
                logging.debug("Session is frozen, skipping idle state change")
                return

            is_asleep = cm.isAsleep()

            if (not idle_hint and is_asleep) or (idle_hint and not is_asleep):
                logging.debug(f"Screen state transition: {is_asleep} -> {not is_asleep}")
                # FakeShell: we need a bit of sleep here after setting the prop since it takes a bit of time for the cache to
                # to invalidate and for hwc_set to pick up our prop and stop serving requests. technically this shouldn't be
                # much of an issue since its a different thread, but being able to eliminate this sleep here would be nice
                if idle_hint:  # Screen going off
                    cm.Setprop("furios.screen_off", "true")
                    time.sleep(1)
                    cm.Screen()
                else:  # Screen going on
                    cm.Screen()
                    time.sleep(1)
                    cm.Setprop("furios.screen_off", "false")
            else:
                logging.debug(f"No screen state change needed. Current: asleep={is_asleep}, idle={idle_hint}")

    def run(self):
        self.args.screenLoop = GLib.MainLoop()
        logging.debug("Screen service running")
        self.args.screenLoop.run()

def service_thread(args):
    global stopping

    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        screen_service = ScreenService(args)

        while not stopping:
            try:
                screen_service.run()
            except Exception as e:
                logging.error(f"Error in screen service loop: {e}")
                if not stopping:
                    continue
                break
    except Exception as e:
        logging.error(f"Screen service error: {str(e)}")

def start(args):
    global stopping
    logging.debug("Starting screen manager service")

    stopping = False
    args.screen_manager = threading.Thread(target=service_thread, args=(args,))
    args.screen_manager.daemon = True
    args.screen_manager.start()

def stop(args):
    global stopping

    logging.debug("Stopping screen manager service")
    stopping = True

    try:
        if hasattr(args, 'screenLoop') and args.screenLoop:
            args.screenLoop.quit()
    except Exception as e:
        logging.error(f"Error stopping notification service: {e}")
