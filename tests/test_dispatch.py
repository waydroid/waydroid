# SPDX-License-Identifier: GPL-3.0-or-later
import re
import sys

import pytest

import tools
from tools import helpers

# argparse renders subparser choices as {a,b,c} in help text
_CHOICES_RE = re.compile(r"\{([a-z0-9,-]+)\}")


def _choices(capsys, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        helpers.arguments()
    out = capsys.readouterr().out
    match = _CHOICES_RE.search(out)
    if not match:
        return []
    return [choice.strip() for choice in match.group(1).split(",")]


def test_dispatch_covers_cli_surface(capsys, monkeypatch):
    actions_list = _choices(capsys, monkeypatch, ["waydroid", "-h"])
    assert actions_list, "could not parse action list from help"

    for action in actions_list:
        table = tools.DISPATCH.get(action)
        assert table is not None, \
            f"action {action!r} is missing from tools.DISPATCH"

        subactions = _choices(capsys, monkeypatch, ["waydroid", action, "-h"])
        if subactions:
            for subaction in subactions:
                assert subaction in table, \
                    f"subaction {action} {subaction!r} is missing from tools.DISPATCH"
        else:
            assert None in table, \
                f"action {action!r} has no subparsers but its table has no None handler"


def test_dispatch_handlers_are_callable():
    for action, table in tools.DISPATCH.items():
        for subaction, handler in table.items():
            assert callable(handler), \
                f"handler for {action} {subaction!r} is not callable"


def test_root_actions_have_handlers():
    for action in tools.ROOT_ACTIONS:
        assert action in tools.DISPATCH, \
            f"root action {action!r} is missing from tools.DISPATCH"


def test_dispatch_entries_declare_guard_flags():
    # A new action must go through _entry() so it cannot silently skip the
    # root or init guards in main().
    for action, entry in tools.DISPATCH.items():
        assert hasattr(entry, "need_root"), \
            f"action {action!r} must declare its root flag via _entry()"
        assert hasattr(entry, "allowed_uninitialized"), \
            f"action {action!r} must declare its uninitialized flag via _entry()"


def test_root_actions_derived_from_dispatch():
    expected = frozenset(
        action for action, entry in tools.DISPATCH.items()
        if entry.need_root)
    assert tools.ROOT_ACTIONS == expected


def test_allowed_uninitialized_derived_from_dispatch():
    expected = frozenset(
        action for action, entry in tools.DISPATCH.items()
        if entry.allowed_uninitialized)
    assert tools.ALLOWED_UNINITIALIZED == expected
