# Copyright 2026 Waydroid contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.config load/save roundtrip."""
import os
import tempfile
import unittest
from types import SimpleNamespace

from tests._mocks import install_mocks

install_mocks()

import tools.config  # noqa: E402
from tools.config.load import load  # noqa: E402
from tools.config.save import save  # noqa: E402


def _make_args(config_path):
    return SimpleNamespace(config=config_path)


class TestConfigLoad(unittest.TestCase):
    """Tests for tools.config.load.load()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._config_path = os.path.join(self._tmpdir, "waydroid.cfg")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_load_missing_file_returns_defaults(self):
        cfg = load(_make_args(self._config_path))
        self.assertIn("waydroid", cfg)
        for key in tools.config.config_keys:
            self.assertIn(key, cfg["waydroid"])
            self.assertEqual(cfg["waydroid"][key],
                             str(tools.config.defaults[key]))

    def test_load_empty_file_returns_defaults(self):
        with open(self._config_path, "w") as f:
            f.write("")
        cfg = load(_make_args(self._config_path))
        self.assertEqual(cfg["waydroid"]["arch"],
                         str(tools.config.defaults["arch"]))

    def test_load_valid_config(self):
        with open(self._config_path, "w") as f:
            f.write("[waydroid]\narch = x86_64\nvendor_type = DBUS\n")
        cfg = load(_make_args(self._config_path))
        self.assertEqual(cfg["waydroid"]["arch"], "x86_64")
        self.assertEqual(cfg["waydroid"]["vendor_type"], "DBUS")

    def test_load_removes_non_configurable_keys(self):
        """Keys in defaults but not in config_keys get deleted from loaded cfg."""
        with open(self._config_path, "w") as f:
            f.write("[waydroid]\narch = arm64\nwork = /custom/path\n")
        cfg = load(_make_args(self._config_path))
        self.assertNotIn("work", cfg["waydroid"])

    def test_load_adds_properties_section(self):
        cfg = load(_make_args(self._config_path))
        self.assertIn("properties", cfg)

    def test_load_configurable_key_from_file(self):
        with open(self._config_path, "w") as f:
            f.write("[waydroid]\nsuspend_action = stop\n")
        cfg = load(_make_args(self._config_path))
        self.assertEqual(cfg["waydroid"]["suspend_action"], "stop")


class TestConfigSave(unittest.TestCase):
    """Tests for tools.config.save.save()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._config_path = os.path.join(self._tmpdir, "sub", "waydroid.cfg")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_save_creates_directory(self):
        args = _make_args(self._config_path)
        cfg = load(args)
        save(args, cfg)
        self.assertTrue(os.path.isfile(self._config_path))

    def test_save_load_roundtrip(self):
        args = _make_args(self._config_path)
        cfg = load(args)
        cfg["waydroid"]["arch"] = "arm64"
        cfg["waydroid"]["vendor_type"] = "DBUS"
        save(args, cfg)

        cfg2 = load(_make_args(self._config_path))
        self.assertEqual(cfg2["waydroid"]["arch"], "arm64")
        self.assertEqual(cfg2["waydroid"]["vendor_type"], "DBUS")

    def test_save_properties_roundtrip(self):
        args = _make_args(self._config_path)
        cfg = load(args)
        cfg["properties"]["ro.test.key"] = "test_value"
        save(args, cfg)

        cfg2 = load(_make_args(self._config_path))
        self.assertEqual(cfg2["properties"]["ro.test.key"], "test_value")


if __name__ == "__main__":
    unittest.main()
