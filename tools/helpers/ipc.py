# Copyright 2022 Alessandro Astone
# Copyright 2025 Bardia Moshiri
# SPDX-License-Identifier: GPL-3.0-or-later

import dbus

def DBusContainerService(object_path="/ContainerManager", intf="io.furios.Andromeda.ContainerManager"):
    return dbus.Interface(dbus.SystemBus().get_object("io.furios.Andromeda.Container", object_path), intf)

def DBusSessionService(object_path="/SessionManager", intf="io.furios.Andromeda.SessionManager"):
    return dbus.Interface(dbus.SessionBus().get_object("io.furios.Andromeda.Session", object_path), intf)
