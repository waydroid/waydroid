# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import tools.config
import tools.helpers.ipc
import tools.helpers.net
import dbus

def print_status(args):
    cfg = tools.config.load(args)
    def print_stopped():
        print("Session:\tSTOPPED")
        print("Vendor type:\t" + cfg["waydroid"]["vendor_type"])

    try:
        session = tools.helpers.ipc.DBusContainerService().GetSession()
        if session:
            print("Session:\tRUNNING")
            print("Container:\t" + session["state"])
            print("Vendor type:\t" + cfg["waydroid"]["vendor_type"])
            print("IP address:\t" + (tools.helpers.net.get_device_ip_address() or "UNKNOWN"))
            print("Session user:\t{}({})".format(session["user_name"], session["user_id"]))
            print("Wayland display:\t" + session["wayland_display"])
        else:
            print_stopped()
    except dbus.DBusException:
        print_stopped()
