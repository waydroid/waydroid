# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading
from tools.interfaces import IClipboard

try:
    import pyclip
    canClip = True
except Exception as e:
    logging.debug(str(e))
    canClip = False

stopping = False

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
        while not stopping:
            IClipboard.add_service(args, sendClipboardData, getClipboardData)

    if canClip:
        global stopping
        stopping = False
        args.clipboard_manager = threading.Thread(target=service_thread)
        args.clipboard_manager.start()
    else:
        logging.debug("Skipping clipboard manager service because of missing pyclip package")

def stop(args):
    global stopping
    stopping = True
    try:
        if args.clipboardLoop:
            args.clipboardLoop.quit()
    except AttributeError:
        logging.debug("Clipboard service is not even started")
