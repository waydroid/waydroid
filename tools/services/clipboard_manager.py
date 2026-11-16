# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading
import tools.config
from tools.interfaces import IClipboard

try:
    import pyclip
    canClip = True
except Exception as e:
    logging.debug(str(e))
    canClip = False

stopping = threading.Event()

def start(args):
    def sendClipboardData(value):
        try:
            pyclip.copy(value)
        except Exception as e:
            logging.debug(str(e))

    def getClipboardData():
        try:
            return pyclip.paste()
        except Exception as e:
            logging.debug(str(e))
        return ""

    def service_thread():
        while not stopping.is_set():
            if not IClipboard.add_service(args, sendClipboardData, getClipboardData):
                stopping.wait(tools.config.binder_service_retry_interval)

    if canClip:
        stopping.clear()
        args.clipboard_manager = threading.Thread(target=service_thread)
        args.clipboard_manager.start()
    else:
        logging.debug("Skipping clipboard manager service because of missing pyclip package")

def stop(args):
    stopping.set()
    try:
        if args.clipboardLoop:
            args.clipboardLoop.quit()
    except AttributeError:
        logging.debug("Clipboard service is not even started")
