# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import dbus
import dbus.service
import dbus.mainloop.glib
import threading
import time
import queue
from gi.repository import GLib
from tools import helpers

stopping = False

class ScreenService:
    def __init__(self, args):
        self.args = args
        self.session_id = None
        self.idle_queue = queue.Queue()
        self.processing = False
        self.queue_lock = threading.Lock()
        self.last_idle_state = None
        self.last_processed_time = 0

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.session_id = self.get_session_id()
        logging.debug(f"Initial session ID: {self.session_id}")
        self.setup_dbus_signals()

        # Start the queue processor thread
        self.queue_thread = threading.Thread(target=self.process_idle_queue)
        self.queue_thread.daemon = True
        self.queue_thread.start()

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
            logging.debug(f"IdleHint changed: {idle_hint}")

            current_time = time.time()
            if self.last_idle_state == idle_hint and current_time - self.last_processed_time < 0.5:
                logging.debug(f"Ignoring duplicate idle_hint={idle_hint} change that came too quickly")
                return

            # Add the idle hint change to the queue
            self.idle_queue.put((idle_hint, current_time))
            logging.debug(f"Added idle_hint={idle_hint} to processing queue. Queue size: {self.idle_queue.qsize()}")

    def _verify_screen_state(self, expected_idle_hint):
        # wait for wakefulness to settle before we continue to get an accurate result
        time.sleep(3)

        try:
            cm = helpers.ipc.DBusContainerService()
            is_asleep = cm.isAsleep()
            current_prop = cm.Getprop("furios.screen_off")

            logging.debug(f"Final state verification - Expected idle: {expected_idle_hint}, Current: prop={current_prop}, asleep={is_asleep}")

            if expected_idle_hint: # For screen OFF (idle=True)
                expected_prop = "true"
                if current_prop != expected_prop or not is_asleep:
                    logging.debug(f"Final state mismatch for OFF state, fixing - prop={current_prop}, asleep={is_asleep}")
                    if current_prop != expected_prop:
                        cm.Setprop("furios.screen_off", expected_prop)
                        time.sleep(1)
                    if not is_asleep:
                        cm.Screen()
            else: # For screen ON (idle=False)
                expected_prop = "false"
                if current_prop != expected_prop or is_asleep:
                    logging.debug(f"Final state mismatch for ON state, fixing - prop={current_prop}, asleep={is_asleep}")
                    if is_asleep:
                        cm.Screen()
                        time.sleep(1)
                    if current_prop != expected_prop:
                        cm.Setprop("furios.screen_off", expected_prop)

            final_prop = cm.Getprop("furios.screen_off")
            final_asleep = cm.isAsleep()
            logging.debug(f"Final screen state after verification: prop={final_prop}, asleep={final_asleep}")
        except Exception as e:
            logging.error(f"Error during final verification: {e}")

    def process_idle_queue(self):
        global stopping

        while not stopping:
            try:
                idle_hint_data = self.idle_queue.get()

                if isinstance(idle_hint_data, tuple):
                    idle_hint, timestamp = idle_hint_data
                else:
                    idle_hint = idle_hint_data
                    timestamp = time.time()

                with self.queue_lock:
                    self.processing = True

                    if not self.idle_queue.empty():
                        # Skip all intermediate events and get only the last one
                        skipped_count = 0
                        last_event = None

                        while not self.idle_queue.empty():
                            last_event = self.idle_queue.get()
                            skipped_count += 1
                            self.idle_queue.task_done()

                        # Only process the current event if it's being processed already
                        # Then process the last event only
                        logging.debug(f"Processing current idle_hint={idle_hint} from queue")
                        self._handle_idle_hint(idle_hint)

                        # Process the last event in the queue
                        if last_event:
                            if isinstance(last_event, tuple):
                                last_idle_hint, last_timestamp = last_event
                            else:
                                last_idle_hint = last_event
                                last_timestamp = time.time()

                            logging.debug(f"Skipped {skipped_count-1} intermediate events, processing last event: {last_idle_hint}")
                            self._handle_idle_hint(last_idle_hint)
                            idle_hint = last_idle_hint
                    else:
                        # Just process the current event if it's the only one
                        logging.debug(f"Processing idle_hint={idle_hint} from queue (only event)")
                        self._handle_idle_hint(idle_hint)

                    self.last_idle_state = idle_hint
                    self.last_processed_time = time.time()

                    self.idle_queue.task_done()
                    self.processing = False

                    # Always perform the final check after processing the last event
                    self._verify_screen_state(idle_hint)
                    logging.debug(f"Queue processing complete. Final idle state: {idle_hint}")
            except Exception as e:
                logging.error(f"Error processing idle hint from queue: {e}")
                self.idle_queue.task_done()
                self.processing = False
            time.sleep(0.1)

    def _handle_idle_hint(self, idle_hint):
        try:
            cm = helpers.ipc.DBusContainerService()
            session = cm.GetSession()
            if session["state"] == "FROZEN":
                logging.debug("Session is frozen, skipping idle state change")
                return

            is_asleep = cm.isAsleep()
            current_prop = cm.Getprop("furios.screen_off")
            logging.debug(f"Current screen_off property: {current_prop}, idle_hint: {idle_hint}, is_asleep: {is_asleep}")

            # FakeShell: we need a bit of sleep here after setting the prop since it takes a bit of time for the cache to
            # to invalidate and for hwc_set to pick up our prop and stop serving requests. technically this shouldn't be
            # much of an issue since its a different thread, but being able to eliminate this sleep here would be nice
            if not idle_hint: # Handle screen on (not idle)
                if is_asleep or current_prop == "true":
                    logging.debug(f"Turning screen ON: prop={current_prop}, asleep={is_asleep}")
                    cm.Screen()
                    time.sleep(1)
                    cm.Setprop("furios.screen_off", "false")
                else:
                    logging.debug(f"Screen already ON: prop={current_prop}, asleep={is_asleep}")
            else: # Handle screen off (idle)
                if not is_asleep or current_prop == "false":
                    logging.debug(f"Turning screen OFF: prop={current_prop}, asleep={is_asleep}")
                    cm.Setprop("furios.screen_off", "true")
                    time.sleep(1)
                    cm.Screen()
                else:
                    logging.debug(f"Screen already OFF: prop={current_prop}, asleep={is_asleep}")
        except Exception as e:
            logging.error(f"Error handling idle hint {idle_hint}: {e}")

    def run(self):
        self.args.screenLoop = GLib.MainLoop()
        logging.debug("Screen service running")
        self.args.screenLoop.run()

    def shutdown(self):
        if self.idle_queue.qsize() > 0:
            logging.debug(f"Waiting for {self.idle_queue.qsize()} pending idle hint tasks to complete")
            self.idle_queue.join()

def service_thread(args):
    global stopping

    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        screen_service = ScreenService(args)
        args.screen_service = screen_service

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
        if hasattr(args, 'screen_service'):
            args.screen_service.shutdown()
        if hasattr(args, 'screenLoop') and args.screenLoop:
            args.screenLoop.quit()
    except Exception as e:
        logging.error(f"Error stopping screen manager service: {e}")
