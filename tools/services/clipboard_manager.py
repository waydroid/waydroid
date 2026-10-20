# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from tools.interfaces import IClipboard
from tools.services.runner import ServiceRunner

try:
    import pyclip
    canClip = True
except Exception as e:
    logging.debug(str(e))
    canClip = False

runner = ServiceRunner("Clipboard", "clipboardLoop")

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

    if not canClip:
        logging.debug("Skipping clipboard manager service because of missing pyclip package")
        return

    runner.start(lambda: IClipboard.add_service(args, sendClipboardData, getClipboardData))

def stop(args):
    runner.stop(args)
