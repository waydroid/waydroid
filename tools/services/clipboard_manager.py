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
        except UnicodeDecodeError as e:
            logging.debug("sendClipboardData: UnicodeDecodeError: %s", str(e))
            logging.debug("During handling of the above exception, the data causing the error was: %s", value)
        except Exception as e:
            logging.debug(f"sendClipboardData: Exception: {str(e)} occurred with {value}")

    def get_clipboard_via_xsel():
        import subprocess
        try:
            return subprocess.check_output(['xsel', '--output', '--clipboard']).decode('utf-8')
        except subprocess.CalledProcessError as e:
            print("An error occurred while trying to read the clipboard using xsel.")
            return ""

    def getClipboardData():
        try:
            # Attempt to get clipboard data using pyclip
            return pyclip.paste()
        except Exception as e:
            logging.debug(f"getClipboardData: Exception with pyclip: {str(e)}")

        try:
            # Fallback to xsel if pyclip fails with: `'utf-8' codec can't decode byte 0xfd in position 0: invalid start byte`
            xsel_data = get_clipboard_via_xsel()
            logging.debug("getClipboardData: Successfully retrieved data using xsel.")
            return xsel_data
        except Exception as e:
            logging.debug(f"getClipboardData: Exception with xsel: {str(e)}")

        logging.debug("getClipboardData: Failed to retrieve data from clipboard.")
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
        logging.warning("Skipping clipboard manager service because of missing pyclip package")

def stop(args):
    global stopping
    stopping = True
    try:
        if args.clipboardLoop:
            args.clipboardLoop.quit()
    except AttributeError:
        logging.debug("Clipboard service is not even started")
