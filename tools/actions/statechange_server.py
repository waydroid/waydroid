# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later
import socket
import subprocess
import threading
import logging
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import tools.config
from tools import helpers
import signal
import sys
import os
import time

NETLINK_KOBJECT_UEVENT = 15
BUFFER_SIZE = 4096
ROOTFS_PATH = '/var/lib/waydroid/rootfs'

running = False
mainloop = None
state_change = None

def signal_handler(signum, frame):
    global running
    logging.info(f"Received signal {signum}, shutting down...")
    running = False
    stop()

class StateChangeInterface(dbus.service.Object):
    def __init__(self, bus_name):
        super().__init__(bus_name, '/id/waydro/StateChange')
        self.composer_monitor_thread = None
        self.monitor_thread = None
        self.package_monitor_thread = None
        self.clipboard_monitor_thread = None
        self.gnss_monitor_thread = None
        self.stop_monitoring = False
        self.current_watch_process = None

    @dbus.service.signal(dbus_interface='id.waydro.StateChange', signature='i')
    def userUnlocked(self, uid):
        logging.info("Signal: userUnlocked emitted")
        pass

    @dbus.service.signal(dbus_interface='id.waydro.StateChange', signature='isi')
    def packageStateChanged(self, action, name, uid):
        logging.info(f"Signal: packageStateChanged emitted: action={action}, name={name}, uid={uid}")
        pass

    @dbus.service.signal(dbus_interface='id.waydro.StateChange', signature='s')
    def sendClipboardData(self, content):
        logging.info(f"Signal: sendClipboardData emitted: content={content}")
        pass

    @dbus.service.signal(dbus_interface='id.waydro.StateChange', signature='b')
    def gnssStateChanged(self, state):
        logging.info(f"Signal: gnssStateChanged emitted: state={state}")
        pass

    def propwatch(self, propname):
        command = ["lxc-attach", "-P", tools.config.defaults["lxc"], "-n", "waydroid", "--clear-env", "--", "propwatch", propname]
        try:
            self.current_watch_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            if self.current_watch_process and self.current_watch_process.stdout:
                result = self.current_watch_process.stdout.readline().strip()
                return result
            else:
                logging.error(f"Failed to watch the prop {propname}: Process or stdout is None")
                return None
        except Exception as e:
            logging.error(f"Failed to watch the prop {propname}: {e}")
            return None
        finally:
            if self.current_watch_process:
                self.current_watch_process.terminate()
                self.current_watch_process = None

    def is_rootfs_mounted(self):
        with open('/proc/mounts', 'r') as f:
            for line in f:
                if ROOTFS_PATH in line.split():
                    return True
        return False

    def monitor_package_state(self):
        initial_name = helpers.lxc.getprop("furios.android.package.name")
        while not self.stop_monitoring and running:
            try:
                if not self.is_rootfs_mounted():
                    logging.info("Rootfs unmounted in package monitor")
                    break

                new_name = self.propwatch("furios.android.package.name")
                if new_name is None:
                    time.sleep(5)
                    continue

                if new_name and new_name != initial_name:
                    action = helpers.lxc.getprop("furios.android.package.action")
                    uid = int(helpers.lxc.getprop("furios.android.package.uid"))
                    self.packageStateChanged(int(action), new_name, int(uid))
                    initial_name = new_name
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error monitoring package state: {e}")
                time.sleep(5)

    def monitor_clipboard(self):
        initial_count = helpers.lxc.getprop("furios.android.clipboard.count")
        while not self.stop_monitoring and running:
            try:
                if not self.is_rootfs_mounted():
                    logging.info("Rootfs unmounted in clipboard monitor")
                    break

                new_count = self.propwatch("furios.android.clipboard.count")
                if new_count is None:
                    time.sleep(5)
                    continue

                if new_count and new_count != "0" and new_count != initial_count:
                    host_data_path = helpers.lxc.getprop("waydroid.host_data_path")
                    clipboard_path = os.path.join(host_data_path, "clipboard", "clipboard")

                    if os.path.isdir(os.path.dirname(clipboard_path)) and os.path.isfile(clipboard_path):
                        try:
                            with open(clipboard_path, 'r') as f:
                                content = f.read()
                            self.sendClipboardData(content)
                        except Exception as e:
                            logging.error(f"Error reading clipboard file: {e}")
                    initial_count = new_count
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error monitoring clipboard: {e}")
                time.sleep(5)

    def monitor_gnss_state(self):
        initial_state = helpers.lxc.getprop("furios.gnss.active")

        try:
            if initial_state:
                initial_state = bool(int(initial_state))
            else:
                logging.error("initial GNSS state is an empty string, defaulting to false")
                initial_state = False
        except Exception as e:
            logging.error(f"Failed to convert initial state to boolean: {e}")
            initial_state = False

        while not self.stop_monitoring and running:
            try:
                if not self.is_rootfs_mounted():
                    logging.info("Rootfs unmounted in GNSS monitor")
                    break

                new_state = self.propwatch("furios.gnss.active")
                if new_state is None:
                    time.sleep(5)
                    continue

                try:
                    if new_state:
                        new_state = bool(int(new_state))
                    else:
                        # give it one more shot, perhaps a false alarm from propwatch
                        state = helpers.lxc.getprop("furios.gnss.active")
                        if state:
                            new_state = bool(int(state))
                        else:
                            logging.error("new GNSS state is an empty string, defaulting to false")
                            new_state = False
                            time.sleep(2)
                except Exception as e:
                    logging.error(f"Failed to convert new state to boolean: {e}")
                    new_state = False

                if new_state != initial_state:
                    self.gnssStateChanged(new_state)
                    initial_state = new_state
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error monitoring gnss state: {e}")
                time.sleep(5)

    def monitor_composer(self):
        initial_state = helpers.lxc.getprop("init.svc.vendor.hwcomposer-2-1")
        while not self.stop_monitoring and running:
            try:
                if not self.is_rootfs_mounted():
                    logging.info("Rootfs unmounted in composer monitor")
                    break

                new_state = self.propwatch("init.svc.vendor.hwcomposer-2-1")
                if new_state is None:
                    time.sleep(5)
                    continue

                if new_state and new_state != initial_state and new_state == "running":
                    time.sleep(5)
                    command = ["lxc-attach", "-P", tools.config.defaults["lxc"], "-n", "waydroid", "--clear-env", "--", "lshal", "-i", "2>/dev/null", "|", "grep", "vendor.waydroid.display@1.0::IWaydroidDisplay/default"]
                    result = ''

                    current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                    if current_process and current_process.stdout:
                        result = current_process.stdout.readline().strip()
                    else:
                        logging.error(f"Failed to get waydroid display: Process or stdout is None")

                    if result and result == 'vendor.waydroid.display@1.0::IWaydroidDisplay/default':
                        logging.info("vendor.hwcomposer-2-1 is up with all interfaces")
                        break
                    else:
                        pid = helpers.lxc.getprop("init.svc_debug_pid.vendor.hwcomposer-2-1")
                        if pid:
                            logging.info(f"vendor.hwcomposer-2-1 is stuck. killing pid {pid}")
                            command = ["lxc-attach", "-P", tools.config.defaults["lxc"], "-n", "waydroid", "--clear-env", "--", "kill", "-9", f"{pid}"]
                            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                        break
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error monitoring composer state: {e}")
                time.sleep(5)

    def start_watchers(self):
        if self.package_monitor_thread and self.package_monitor_thread.is_alive():
            return

        self.package_monitor_thread = threading.Thread(target=self.monitor_package_state)
        self.clipboard_monitor_thread = threading.Thread(target=self.monitor_clipboard)
        self.gnss_monitor_thread = threading.Thread(target=self.monitor_gnss_state)
        self.package_monitor_thread.start()
        self.clipboard_monitor_thread.start()
        self.gnss_monitor_thread.start()

    def stop_watchers(self):
        self.stop_monitoring = True

        if self.package_monitor_thread and self.package_monitor_thread.is_alive():
            self.package_monitor_thread.join(timeout=2)
            self.package_monitor_thread = None

        if self.clipboard_monitor_thread and self.clipboard_monitor_thread.is_alive():
            self.clipboard_monitor_thread.join(timeout=2)
            self.clipboard_monitor_thread = None

        if self.gnss_monitor_thread and self.gnss_monitor_thread.is_alive():
            self.gnss_monitor_thread.join(timeout=2)
            self.gnss_monitor_thread = None

        self.stop_monitoring = False

    def wait_for_netlink_event(self):
        sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_KOBJECT_UEVENT)
        try:
            sock.bind((0, -1))
            data = sock.recv(BUFFER_SIZE)
            messages = data.decode('utf-8', errors='ignore').split('\0')
            event_info = {}
            for message in messages:
                if '=' in message:
                    key, value = message.split('=', 1)
                    event_info[key] = value

            return (event_info.get("SUBSYSTEM") == "block" and event_info.get("ACTION") in {"add", "remove", "change"})
        except socket.error:
            if not running:
                return True
            return False
        finally:
            sock.close()

    def monitor_main(self):
        while running:
            if self.is_rootfs_mounted():
                logging.info("Rootfs is mounted")
                if helpers.lxc.getprop("furios.android.userunlocked") == "true":
                    logging.info("User is already unlocked")
                    self.userUnlocked(0)
                    self.start_watchers()
                else:
                    self.composer_monitor_thread = threading.Thread(target=self.monitor_composer)
                    self.composer_monitor_thread.start()
                    logging.info("Waiting for user unlock")
                    while running and self.is_rootfs_mounted():
                        result = self.propwatch("furios.android.userunlocked")
                        if result == "true":
                            logging.info("User unlocked")
                            self.userUnlocked(0)

                            if self.composer_monitor_thread and self.composer_monitor_thread.is_alive():
                                self.composer_monitor_thread.join(timeout=2)
                                self.composer_monitor_thread = None

                            self.start_watchers()
                            break

                while running and self.is_rootfs_mounted():
                    if self.wait_for_netlink_event():
                        if not self.is_rootfs_mounted():
                            break

                logging.info("Rootfs unmounted, stopping watchers")
                self.stop_watchers()
            else:
                logging.info("Waiting for rootfs to be mounted")
                while running and not self.is_rootfs_mounted():
                    if self.wait_for_netlink_event():
                        if self.is_rootfs_mounted():
                            break
def run_mainloop():
    global mainloop
    mainloop = GLib.MainLoop()
    try:
        mainloop.run()
    except (KeyboardInterrupt, SystemExit):
        stop()

def start(_args=None):
    global running, state_change
    if running:
        return

    running = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    name = dbus.service.BusName('id.waydro.StateChange', bus)

    state_change = StateChangeInterface(name)
    state_change.monitor_thread = threading.Thread(target=state_change.monitor_main)
    state_change.monitor_thread.start()

    run_mainloop()

def stop(_args=None):
    global running, mainloop, state_change
    if not running:
        return

    running = False
    logging.info("Stopping service...")

    if state_change:
        state_change.stop_monitoring = True
        if state_change.monitor_thread and state_change.monitor_thread.is_alive():
            state_change.monitor_thread.join(timeout=2)
        state_change.stop_watchers()

    if mainloop:
        mainloop.quit()

    logging.info("Service stopped")
    sys.exit(0)
