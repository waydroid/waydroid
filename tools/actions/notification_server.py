# Copyright 2023 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import sys
import time
import logging
import threading
import subprocess
import dbus
import dbus.service
from collections import defaultdict

running = False
loop_thread = None

class INotification(dbus.service.Object):
    def __init__(self, bus_name, object_path='/id/waydro/Notification'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.signal(dbus_interface='id.waydro.Notification', signature='si')
    def NewMessage(self, package_name, count):
        pass

def get_notifications(old_notification):
    global running
    notification_count = defaultdict(int)

    system_bus = dbus.SystemBus()
    bus_name = dbus.service.BusName('id.waydro.Notification', system_bus)
    interface = INotification(bus_name, object_path='/id/waydro/Notification')

    notification_command = [
        "lxc-attach", "-P", "/var/lib/waydroid/lxc",
        "-n", "waydroid", "--clear-env", "--", "/system/bin/sh", "-c", "dumpsys notification"
    ]

    applist_command = [
        "lxc-attach", "-P", "/var/lib/waydroid/lxc",
        "-n", "waydroid", "--clear-env", "--", "/system/bin/sh", "-c", "pm list packages -3"
    ]

    logging.info("Starting notification server service")

    while running:
        notification_process = subprocess.Popen(notification_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        notification_stdout, notification_stderr = notification_process.communicate()

        if notification_stderr:
            time.sleep(3)
            continue

        notification_stdout = notification_stdout.decode()
        notification_filtered_output = re.findall(r"NotificationRecord.*", notification_stdout)

        applist_process = subprocess.Popen(applist_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        applist_stdout, applist_stderr = applist_process.communicate()

        if applist_stderr:
            time.sleep(3)
            continue

        applist_stdout = applist_stdout.decode()
        packages = [line.split(':')[1] for line in applist_stdout.splitlines() if ':' in line]

        for line in notification_filtered_output:
            fields = line.split("|")

            if len(fields) > 1:
                notification_name = fields[1].strip()
                if notification_name in packages:
                    notification_count[notification_name] += 1

        for package_name, count in notification_count.items():
            old_count = old_notification.get(package_name, 0)

            if count > old_count:
                # logging.info(f"You have {count} notifications from {package_name}")
                interface.NewMessage(package_name, count)

        old_notification = notification_count.copy()
        notification_count = defaultdict(int)
        time.sleep(3)

def start(args):
    global running
    global loop_thread

    running = True
    loop_thread = threading.Thread(target=get_notifications, args=({},))
    loop_thread.start()

def stop(args):
    global running
    global loop_thread

    running = False
    if loop_thread is not None:
        loop_thread.join()
