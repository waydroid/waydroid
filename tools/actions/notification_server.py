# Copyright 2023 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import time
import socket
import logging
import threading
import subprocess
import dbus
import dbus.service

NETLINK_KOBJECT_UEVENT = 15
BUFFER_SIZE = 4096

ROOTFS_PATH = '/var/lib/waydroid/rootfs'

running = False
loop_thread = None

class INotification(dbus.service.Object):
    def __init__(self, bus_name, object_path='/id/waydro/Notification'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.signal(dbus_interface='id.waydro.Notification', signature='ssssssbbbt')
    def NewMessage(self, msg_hash, msg_id, package_name, ticker, title, text, is_foreground_service,
                   is_group_summary, show_light, when):
        pass

    @dbus.service.signal(dbus_interface='id.waydro.Notification', signature='sssssssbbbt')
    def UpdateMessage(self, msg_hash, replaces_hash, msg_id, package_name, ticker, title, text,
                      is_foreground_service, is_group_summary, show_light, when):
        pass

    @dbus.service.signal(dbus_interface='id.waydro.Notification', signature='s')
    def DeleteMessage(self, msg_hash):
        pass

def is_mounted(path):
    with open('/proc/mounts', 'r') as f:
        for line in f:
            if path in line.split():
                return True
    return False

def monitor_mounts():
    sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_KOBJECT_UEVENT)
    sock.bind((0, -1))

    try:
        while True:
            data = sock.recv(BUFFER_SIZE)
            messages = data.decode('utf-8', errors='ignore').split('\0')
            event_info = {}
            for message in messages:
                if '=' in message:
                    key, value = message.split('=', 1)
                    event_info[key] = value

            if event_info.get("SUBSYSTEM") == "block" and event_info.get("ACTION") in {"add", "remove", "change"}:
                if is_mounted(ROOTFS_PATH):
                    break
    except Exception:
        pass
    finally:
        sock.close()

def get_notifications(_old_notification):
    notifications = {}
    old_notifications = {}

    system_bus = dbus.SystemBus()
    bus_name = dbus.service.BusName('id.waydro.Notification', system_bus)
    interface = INotification(bus_name, object_path='/id/waydro/Notification')

    notification_command = [
        "lxc-attach", "-P", "/var/lib/waydroid/lxc", "-n", "waydroid", "--clear-env", "--",
        "/system/bin/sh", "-c", "dumpsys notification --noredact"
    ]

    applist_command = [
        "lxc-attach", "-P", "/var/lib/waydroid/lxc", "-n", "waydroid", "--clear-env", "--",
        "/system/bin/sh", "-c", "pm list packages -3"
    ]

    logging.info("Starting notification server service")

    while running:
        if not is_mounted(ROOTFS_PATH):
            monitor_mounts()

        notification_process = subprocess.Popen(notification_command, stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE)
        notification_stdout, notification_stderr = notification_process.communicate()

        if notification_stderr:
            for line in notification_stderr.splitlines():
                logging.error(line)

            time.sleep(3)
            continue

        notification_stdout = notification_stdout.decode()

        applist_process = subprocess.Popen(applist_command, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
        applist_stdout, applist_stderr = applist_process.communicate()

        if applist_stderr:
            time.sleep(3)
            continue

        applist_stdout = applist_stdout.decode()
        packages = [line.split(':')[1] for line in applist_stdout.splitlines() if ':' in line]

        # parse notifications
        current_msg_hash = None
        multiline_ticker = None
        multiline_text = None
        for line in notification_stdout.splitlines():
            # ticker and text may be multi line and there seems no better way
            # to parse this with the dumpsys format
            if multiline_ticker:
                if line.startswith("  "):
                    notifications[current_msg_hash]['ticker'] = multiline_ticker
                    multiline_ticker = None
                else:
                    multiline_ticker = multiline_ticker + "\n" + line
                    continue
            elif multiline_text:
                if line.startswith("  "):
                    notifications[current_msg_hash]['text'] = multiline_text[:-1]
                    multiline_text = None
                else:
                    multiline_text = multiline_text + "\n" + line
                    continue

            if "NotificationRecord" in line:
                current_msg_hash = None
                fields = line.split("|")
                if len(fields) > 3:
                    package_name = fields[1].strip()
                    res = re.search(r'NotificationRecord\(([^:]+):', line)
                    if package_name in packages and res:
                        current_msg_hash = res.group(1)
                        notifications[current_msg_hash] = {
                            'package_name': package_name,
                            'msg_id': fields[2],
                            'ticker': '',
                            'title': '',
                            'text': '',
                            'is_foreground_msg': False,
                            'is_group_summary': False,
                            'show_light': False,
                            'when': 0
                        }
            elif current_msg_hash:
                msg_hash = current_msg_hash

                if "  tickerText=" in line:
                    multiline_ticker = line.replace('tickerText=','').strip()
                elif "  android.title=" in line:
                    res = re.search(r'android.title=\w+\s*\((.*)\)$', line)
                    if res:
                        notifications[msg_hash]['title'] = res.group(1).strip()
                elif "  android.text=" in line:
                    res = re.search(r'android.text=\w+\s*\((.*)$', line)
                    if res:
                        multiline_text = res.group(1).strip()
                elif "  flags=" in line:
                    flags = int(line.replace('flags=','').strip(), 0)
                    notifications[msg_hash]['is_foreground_msg'] = \
                      (flags & 0x00000040) != 0
                    notifications[msg_hash]['is_group_summary'] = \
                      (flags & 0x00000200) != 0
                elif "  mLight=" in line:
                    notifications[msg_hash]['show_light'] = \
                      line.replace('mLight=','').strip() != "null"
                elif "  when=" in line:
                    notifications[msg_hash]['when'] = \
                      int(line.replace('when=','').strip(), 0)

        # analyse and send notifications
        updated_hashes = set()
        for msg_hash, n in notifications.items():
            # this happens e.g. for foreground applications when they start.
            # currently they are ignored, but they could also be transformed
            # into a "<app> started in background" message
            if (n['ticker'] == 'null' or n['ticker'] == '') and (n['title'] == '' or n['text'] == ''):
                logging.error("Ticker is null and title or text are empty. skipping")
                continue

            # check if notification is new or an update (= message hash did not exist before)
            if msg_hash not in old_notifications:
                # search for msg_id in old notifications to see if this is an update
                is_update_of = [h for h, o in old_notifications.items()
                                if o['msg_id'] == n['msg_id']]
                if is_update_of:
                    #logging.info("Update Message (%s):", msg_hash)
                    #logging.info(n)

                    if len(is_update_of) > 1:
                        logging.warning("Warning: Multiple messages w same msg_id at the same time")

                    # send update
                    updated_hashes.add(is_update_of[0])
                    interface.UpdateMessage(msg_hash, is_update_of[0], n['msg_id'],
                                            n['package_name'], n['ticker'], n['title'], n['text'],
                                            n['is_foreground_msg'], n['is_group_summary'],
                                            n['show_light'], n['when'])
                else:
                    #logging.info("New Message (%s):", msg_hash)
                    #logging.info(n)

                    # send new message
                    interface.NewMessage(msg_hash, n['msg_id'], n['package_name'], n['ticker'],
                                         n['title'], n['text'], n['is_foreground_msg'],
                                         n['is_group_summary'], n['show_light'], n['when'])

        # send removal messages
        for msg_hash in old_notifications:
            if msg_hash not in notifications and msg_hash not in updated_hashes:
                #logging.info(f"Send removal message: {msg_hash}")
                interface.DeleteMessage(msg_hash)

        old_notifications = notifications
        notifications = {}
        time.sleep(3)

def start(_args):
    global running
    global loop_thread

    running = True
    loop_thread = threading.Thread(target=get_notifications, args=({},))
    loop_thread.start()

def stop(_args):
    global running

    running = False
    if loop_thread is not None:
        loop_thread.join()
