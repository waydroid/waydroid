# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools/__init__.py helpers (log path selection)."""

import types

import tools
import tools.config


def make_args(user_log=None, log="/var/lib/waydroid/waydroid.log"):
    return types.SimpleNamespace(user_log=user_log, log=log)


def test_log_path_root_uses_own_log(monkeypatch):
    monkeypatch.setattr(tools.os, "geteuid", lambda: 0)
    args = make_args()
    assert tools._log_path(args) == args.log


def test_log_path_nonroot_prefers_root_log_when_readable(monkeypatch):
    monkeypatch.setattr(tools.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(tools.os, "access", lambda path, mode: True)
    args = make_args()
    root_log = tools.config.defaults["work"] + "/waydroid.log"
    assert tools._log_path(args) == root_log


def test_log_path_nonroot_explicit_log_wins(monkeypatch):
    monkeypatch.setattr(tools.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(tools.os, "access", lambda path, mode: True)
    # main() redirects args.log to the explicit -l path before _log runs, so
    # the root-log preference must not kick in even though it is readable.
    args = make_args(user_log="/tmp/custom.log", log="/tmp/custom.log")
    assert tools._log_path(args) == "/tmp/custom.log"


def test_log_path_nonroot_root_log_unreadable(monkeypatch):
    monkeypatch.setattr(tools.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(tools.os, "access", lambda path, mode: False)
    args = make_args()
    assert tools._log_path(args) == args.log
