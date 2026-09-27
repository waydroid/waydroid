# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.config.get_session_defaults()."""

import types

import tools.config


def _patch_user(monkeypatch, name="u", uid=1000, gid=1000):
    monkeypatch.setattr(tools.config.pwd, "getpwuid",
                        lambda real_uid: types.SimpleNamespace(pw_name=name))
    monkeypatch.setattr(tools.config.os, "getuid", lambda: uid)
    monkeypatch.setattr(tools.config.os, "getgid", lambda: gid)
    monkeypatch.setenv("HOME", "/home/" + name)


def test_get_session_defaults_env(monkeypatch):
    _patch_user(monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setenv("PULSE_RUNTIME_PATH", "/run/user/1000/pulse")
    monkeypatch.setenv("XDG_DATA_HOME", "/home/u/.local/share")

    session = tools.config.get_session_defaults()

    assert session["wayland_display"] == "wayland-1"
    assert session["xdg_runtime_dir"] == "/run/user/1000"
    assert session["pulse_runtime_path"] == "/run/user/1000/pulse"
    assert session["user_name"] == "u"
    assert session["user_id"] == "1000"
    assert session["group_id"] == "1000"
    assert session["waydroid_user_state"] == "/home/u/.local/share/waydroid"
    assert session["waydroid_data"] == "/home/u/.local/share/waydroid/data"


def test_get_session_defaults_unset_env(monkeypatch):
    # os.environ.get() yields the literal string "None" when unset;
    # session_manager treats that as "not set" (see its WAYLAND_DISPLAY
    # handling), so pin that behavior here.
    _patch_user(monkeypatch)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("PULSE_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    session = tools.config.get_session_defaults()

    assert session["wayland_display"] == "None"
    assert session["xdg_runtime_dir"] == "None"
    assert session["pulse_runtime_path"] == "None/pulse"
    assert session["waydroid_user_state"] == "/home/u/.local/share/waydroid"


def test_get_session_defaults_pulse_falls_back_to_runtime_dir(monkeypatch):
    _patch_user(monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.delenv("PULSE_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    session = tools.config.get_session_defaults()

    assert session["pulse_runtime_path"] == "/run/user/1000/pulse"
