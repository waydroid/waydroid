# Copyright 2021 Erfan Abdi
# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import dbus
import logging
import threading
from tools.interfaces import IClipboard
from tools.helpers import WaylandClipboardHandler, drivers
import dbus.mainloop.glib
from gi.repository import GLib

stopping = False
clipboard_handler = None

def start(args):
    def setup_dbus_signals():
        global clipboard_handler
        bus = dbus.SystemBus()
        bus.add_signal_receiver(
            clipboard_handler.copy,
            signal_name='sendClipboardData',
            dbus_interface='io.furios.Andromeda.StateChange',
            bus_name='io.furios.Andromeda.StateChange'
        )

    def service_thread_gbinder():
        global clipboard_handler
        try:
            clipboard_handler = WaylandClipboardHandler()
            while not stopping:
                IClipboard.add_service(
                    args,
                    clipboard_handler.copy,
                    clipboard_handler.paste
                )
        except Exception as e:
            logging.debug(f"Clipboard service error: {str(e)}")

    def service_thread_statechange():
        global clipboard_handler

        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

            clipboard_handler = WaylandClipboardHandler()
            setup_dbus_signals()

            args.clipboardLoop = GLib.MainLoop()
            while not stopping:
                try:
                    args.clipboardLoop.run()
                except Exception as e:
                    logging.error(f"Error in clipboard manager loop: {e}")
                    if not stopping:
                        continue
                    break
        except Exception as e:
            logging.debug(f"Clipboard service error: {str(e)}")

    def service_thread():
        if drivers.should_use_statechange():
            service_thread_statechange()
        else:
            service_thread_gbinder()

    global stopping
    stopping = False
    args.clipboard_manager = threading.Thread(target=service_thread)
    args.clipboard_manager.start()

def stop(args):
    global stopping
    stopping = True
    try:
        if args.clipboardLoop:
            args.clipboardLoop.quit()
    except AttributeError:
        logging.debug("Clipboard service is not even started")
