# Copyright 2021 Erfan Abdi
# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import tools.config
import tools.helpers.ipc
import tools.helpers.net
import dbus

def print_status(args):
    cfg = tools.config.load(args)
    def print_stopped():
        print("Session: STOPPED")
        print("Vendor type: " + cfg["andromeda"]["vendor_type"])

    try:
        cm = tools.helpers.ipc.DBusContainerService()
        session = cm.GetSession()
        if session:
            try:
                screen_off = cm.Getprop("furios.screen_off")
                if screen_off == "true":
                    screen_state = "Off"
                elif screen_off == "false" or screen_off == "":
                    screen_state = "On"
                else:
                    screen_state = "On"
            except:
                screen_state = "Unknown"

            try:
                active = cm.Getprop("andromeda.active_apps")
                active_app = active if active else "none"
            except:
                active_app = "none"

            try:
                open = cm.Getprop("andromeda.open_windows")
                open_windows = open if open else "0"
            except:
                open_windows = "0"

            print("Session: RUNNING")
            print("Container: " + session["state"])
            print("Vendor type: " + cfg["andromeda"]["vendor_type"])
            print("IP address: " + (tools.helpers.net.get_device_ip_address() or "UNKNOWN"))
            print("Session user: {}({})".format(session["user_name"], session["user_id"]))
            print("Wayland display: " + session["wayland_display"])
            print(f"Screen state: {screen_state}")
            print(f"Active app: {active_app}")
            print(f"Number of open windows: {open_windows}")
        else:
            print_stopped()
    except dbus.DBusException:
        print_stopped()
