# Copyright 2022 Alessandro Astone
# SPDX-License-Identifier: GPL-3.0-or-later

# Currently implemented as FIFO
import os
import dbus

def create_channel(channel):
    pipe = pipe_for(channel)
    if not os.path.exists(pipe):
        os.mkfifo(pipe)

def open_channel(channel, mode, buffering=0):
    return open(pipe_for(channel), mode, buffering)

def DBusContainerService(object_path="/ContainerManager", intf="id.waydro.ContainerManager"):
    return dbus.Interface(dbus.SystemBus().get_object("id.waydro.Container", object_path), intf)

def DBusSessionService(object_path="/SessionManager", intf="id.waydro.SessionManager"):
    return dbus.Interface(dbus.SessionBus().get_object("id.waydro.Session", object_path), intf)
