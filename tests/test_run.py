# Copyright 2026 Waydroid contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.helpers.run module (flat_cmd)."""
import unittest

from tests._mocks import install_mocks

install_mocks()

from tools.helpers.run import flat_cmd  # noqa: E402


class TestFlatCmd(unittest.TestCase):
    """Tests for flat_cmd() shell escaping."""

    def test_simple_command(self):
        self.assertEqual(flat_cmd(["echo", "hello"]), "echo hello")

    def test_command_with_spaces_in_arg(self):
        result = flat_cmd(["echo", "hello world"])
        self.assertEqual(result, "echo 'hello world'")

    def test_multiple_args(self):
        result = flat_cmd(["ls", "-la", "/tmp"])
        self.assertEqual(result, "ls -la /tmp")

    def test_arg_with_single_quote(self):
        result = flat_cmd(["echo", "it's"])
        self.assertIn("'it'\"'\"'s'", result)

    def test_env_variables(self):
        result = flat_cmd(["make"], env={"JOBS": "4"})
        self.assertEqual(result, "JOBS=4 make")

    def test_multiple_env_variables(self):
        result = flat_cmd(["make"], env={"A": "1", "B": "2"})
        self.assertIn("A=1", result)
        self.assertIn("B=2", result)
        self.assertIn("make", result)

    def test_env_value_with_spaces(self):
        result = flat_cmd(["make"], env={"PATH_EXTRA": "/my dir"})
        self.assertIn("PATH_EXTRA='/my dir'", result)

    def test_working_dir(self):
        result = flat_cmd(["ls"], working_dir="/tmp")
        self.assertEqual(result, "cd /tmp;ls")

    def test_working_dir_with_spaces(self):
        result = flat_cmd(["ls"], working_dir="/my dir")
        self.assertEqual(result, "cd '/my dir';ls")

    def test_env_and_working_dir(self):
        result = flat_cmd(["make"], working_dir="/build", env={"JOBS": "4"})
        self.assertIn("cd /build;", result)
        self.assertIn("JOBS=4", result)

    def test_empty_cmd_list(self):
        self.assertEqual(flat_cmd([]), "")

    def test_dangerous_chars_escaped(self):
        result = flat_cmd(["echo", "$(rm -rf /)"])
        self.assertIn("'$(rm -rf /)'", result)

    def test_semicolon_escaped(self):
        result = flat_cmd(["echo", "a;rm -rf /"])
        self.assertIn("'a;rm -rf /'", result)

    def test_backtick_escaped(self):
        result = flat_cmd(["echo", "`whoami`"])
        self.assertIn("'`whoami`'", result)


if __name__ == "__main__":
    unittest.main()
