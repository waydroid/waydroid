# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared mock installation for tests that import tools.* modules.

Several tools modules transitively import gbinder, dbus, and gi at module
level. These are system dependencies not available in CI, so install stubs
before any test imports tools.*.
"""
import sys
import types


def _mock_module(name, attrs=None):
    mod = types.ModuleType(name)
    if attrs:
        for key, value in attrs.items():
            setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


def install_mocks():
    if "gbinder" not in sys.modules:
        _mock_module("gbinder")

    if "gi" not in sys.modules:
        gi = _mock_module("gi")
        gi_repo = _mock_module("gi.repository")

        class GLib:
            PRIORITY_HIGH = 0

            @staticmethod
            def MainLoop():
                class Loop:
                    def run(self):
                        pass

                    def quit(self):
                        pass

                return Loop()

            @staticmethod
            def timeout_add_seconds(*args):
                pass

            @staticmethod
            def unix_signal_add(*args):
                pass

        gi_repo.GLib = GLib
        gi.repository = gi_repo

    if "dbus" not in sys.modules:
        dbus_mod = _mock_module("dbus")

        class DBusException(Exception):
            pass

        dbus_exceptions = _mock_module(
            "dbus.exceptions", {"DBusException": DBusException})
        dbus_mod.exceptions = dbus_exceptions

        dbus_mainloop = _mock_module("dbus.mainloop")
        dbus_mainloop_glib = _mock_module("dbus.mainloop.glib", {
            "DBusGMainLoop": lambda set_as_default=False: None,
            "threads_init": lambda: None,
        })
        dbus_mainloop.glib = dbus_mainloop_glib
        dbus_mod.mainloop = dbus_mainloop

        dbus_service = _mock_module("dbus.service")

        class ServiceObject:
            def __init__(self, bus=None, path=None):
                pass

        dbus_service.Object = ServiceObject
        dbus_service.method = lambda *a, **k: (lambda f: f)
        dbus_service.signal = lambda *a, **k: (lambda f: f)
        dbus_mod.service = dbus_service

    if "pyclip" not in sys.modules:
        _mock_module("pyclip")
