# Copyright 2026 Waydroid contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.helpers.props module (file_get)."""
import os
import tempfile
import unittest
from types import SimpleNamespace

from tests._mocks import install_mocks

install_mocks()

from tools.helpers.props import file_get  # noqa: E402


class TestFileGet(unittest.TestCase):
    """Tests for props.file_get() build.prop parsing."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._propfile = os.path.join(self._tmpdir, "build.prop")
        self._args = SimpleNamespace()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_props(self, content):
        with open(self._propfile, "w") as f:
            f.write(content)

    def test_simple_prop(self):
        self._write_props("ro.build.version.sdk=33\n")
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.build.version.sdk"), "33")

    def test_multiple_props(self):
        self._write_props(
            "ro.build.version.sdk=33\n"
            "ro.product.model=Pixel\n"
            "ro.build.version.release=13\n"
        )
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.product.model"), "Pixel")

    def test_missing_prop_returns_empty(self):
        self._write_props("ro.build.version.sdk=33\n")
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.nonexistent"), "")

    def test_empty_file_returns_empty(self):
        self._write_props("")
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.build.version.sdk"), "")

    def test_comment_lines_ignored(self):
        self._write_props(
            "# ro.build.version.sdk=99\n"
            "ro.build.version.sdk=33\n"
        )
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.build.version.sdk"), "33")

    def test_blank_lines_ignored(self):
        self._write_props(
            "\n\n"
            "ro.build.version.sdk=33\n"
            "\n"
        )
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.build.version.sdk"), "33")

    def test_value_with_equals_sign(self):
        self._write_props("ro.config.url=http://example.com?a=b\n")
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.config.url"), "http://example.com?a=b")

    def test_empty_value(self):
        self._write_props("ro.empty=\n")
        self.assertEqual(file_get(self._args, self._propfile,
                                  "ro.empty"), "")

    def test_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            file_get(self._args, "/nonexistent/build.prop", "ro.test")

    def test_first_matching_prop_wins(self):
        self._write_props(
            "ro.test=first\n"
            "ro.test=second\n"
        )
        self.assertEqual(file_get(self._args, self._propfile, "ro.test"),
                         "first")


if __name__ == "__main__":
    unittest.main()
