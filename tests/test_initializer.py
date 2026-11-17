# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.actions.initializer.get_vendor_type."""

import tools.actions.initializer as initializer


def _props(values=None):
    values = values or {}

    def host_get(args, key):
        return values.get(key, "")
    return host_get


def test_vendor_type_mainline_when_no_props(monkeypatch):
    monkeypatch.setattr(initializer.helpers.props, "host_get", _props())
    assert initializer.get_vendor_type(object()) == "MAINLINE"


def test_vendor_type_from_vndk(monkeypatch):
    monkeypatch.setattr(
        initializer.helpers.props, "host_get",
        _props({"ro.vndk.version": "30"}))
    assert initializer.get_vendor_type(object()) == "HALIUM_11"


def test_vendor_type_vndk_12l(monkeypatch):
    monkeypatch.setattr(
        initializer.helpers.props, "host_get",
        _props({"ro.vndk.version": "32"}))
    assert initializer.get_vendor_type(object()) == "HALIUM_12L"


def test_vendor_type_from_vendor_api(monkeypatch):
    # Halium 15+ images may not expose ro.vndk.version; fall back to the
    # vendor API level.
    monkeypatch.setattr(
        initializer.helpers.props, "host_get",
        _props({"ro.vendor.build.version.sdk": "35"}))
    assert initializer.get_vendor_type(object()) == "HALIUM_15"


def test_vendor_type_ignores_garbage_props(monkeypatch):
    # Non-numeric props (e.g. "29.0") must not crash init.
    monkeypatch.setattr(
        initializer.helpers.props, "host_get",
        _props({"ro.vndk.version": "29.0",
                "ro.vendor.build.version.sdk": "garbage"}))
    assert initializer.get_vendor_type(object()) == "MAINLINE"


def test_vendor_type_low_vndk_stays_mainline(monkeypatch):
    monkeypatch.setattr(
        initializer.helpers.props, "host_get",
        _props({"ro.vndk.version": "19"}))
    assert initializer.get_vendor_type(object()) == "MAINLINE"
