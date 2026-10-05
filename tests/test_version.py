# Copyright 2026 Waydroid contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.helpers.version module."""
import unittest
from unittest.mock import patch

from tests._mocks import install_mocks

install_mocks()

from tools.helpers.version import versiontuple, kernel_version  # noqa: E402


class TestVersionTuple(unittest.TestCase):
    """Tests for versiontuple()."""

    def test_simple_version(self):
        self.assertEqual(versiontuple("1.2.3"), (1, 2, 3))

    def test_two_part_version(self):
        self.assertEqual(versiontuple("1.2"), (1, 2))

    def test_single_number(self):
        self.assertEqual(versiontuple("5"), (5,))

    def test_long_version(self):
        self.assertEqual(versiontuple("1.2.3.4.5"), (1, 2, 3, 4, 5))

    def test_zero_version(self):
        self.assertEqual(versiontuple("0.0.0"), (0, 0, 0))

    def test_large_numbers(self):
        self.assertEqual(versiontuple("10.20.30"), (10, 20, 30))


class TestKernelVersion(unittest.TestCase):
    """Tests for kernel_version()."""

    @patch("os.uname")
    def test_standard_kernel(self, mock_uname):
        mock_uname.return_value = type("U", (), {"release": "6.1.0-generic"})()
        self.assertEqual(kernel_version(), (6, 1))

    @patch("os.uname")
    def test_kernel_with_rc(self, mock_uname):
        mock_uname.return_value = type("U", (), {"release": "6.2.0-rc1"})()
        self.assertEqual(kernel_version(), (6, 2))

    @patch("os.uname")
    def test_kernel_single_digit_minor(self, mock_uname):
        mock_uname.return_value = type("U", (), {"release": "5.0-generic"})()
        self.assertEqual(kernel_version(), (5, 0))


if __name__ == "__main__":
    unittest.main()
