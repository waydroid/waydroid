# SPDX-License-Identifier: GPL-3.0-or-later
"""Pytest configuration.

The waydroid ``tools`` package imports heavy runtime dependencies (dbus,
PyGObject, gbinder) at module import time. The pure-logic helpers under test
(arch, protocol, images, mount) don't use any of them, so we stub them out in
``sys.modules`` to keep the test suite runnable in a minimal environment
(e.g. CI without those native packages installed).
"""

import sys
import types
from unittest.mock import MagicMock

HEAVY_DEPS = [
    "dbus",
    "dbus.exceptions",
    "dbus.mainloop.glib",
    "dbus.service",
    "gbinder",
    "gi",
    "gi.repository",
    "gi.repository.GLib",
]


class _StubModule(types.ModuleType):
    """A module that answers any attribute access with a MagicMock."""

    def __getattr__(self, attr):
        return MagicMock()


def _install_stub(name):
    if name in sys.modules:
        return
    module = _StubModule(name)
    sys.modules[name] = module
    # Make dotted names importable (e.g. `import dbus.mainloop.glib`).
    parts = name.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        if parent not in sys.modules:
            sys.modules[parent] = _StubModule(parent)


for _name in HEAVY_DEPS:
    _install_stub(_name)
