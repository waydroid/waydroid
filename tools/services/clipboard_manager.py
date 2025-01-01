# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading
from tools.interfaces import IClipboard
from tools.helpers import WaylandClipboardHandler

stopping = False
clipboard_handler = None

def start(args):
    def service_thread():
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
