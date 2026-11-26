# Copyright 2026 Waydroid contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.helpers.images module (sha256sum)."""
import hashlib
import os
import tempfile
import unittest

from tests._mocks import install_mocks

install_mocks()

from tools.helpers.images import sha256sum  # noqa: E402


class TestSha256sum(unittest.TestCase):
    """Tests for images.sha256sum()."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_file(self, content, name="test.bin"):
        path = os.path.join(self._tmpdir, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def _hash_file(self, path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def test_empty_file(self):
        path = self._write_file(b"")
        with open(path, "rb") as f:
            self.assertEqual(sha256sum(f), self._hash_file(path))

    def test_simple_content(self):
        path = self._write_file(b"hello world")
        with open(path, "rb") as f:
            self.assertEqual(sha256sum(f), self._hash_file(path))

    def test_binary_content(self):
        path = self._write_file(bytes(range(256)) * 10)
        with open(path, "rb") as f:
            self.assertEqual(sha256sum(f), self._hash_file(path))

    def test_large_file(self):
        path = self._write_file(os.urandom(1024 * 1024))
        with open(path, "rb") as f:
            self.assertEqual(sha256sum(f), self._hash_file(path))

    def test_known_hash(self):
        path = self._write_file(b"abc")
        expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        with open(path, "rb") as f:
            self.assertEqual(sha256sum(f), expected)

    def test_file_pointer_reset_after_hash(self):
        path = self._write_file(b"content")
        with open(path, "rb") as f:
            sha256sum(f)
            self.assertEqual(f.tell(), 0)

    def test_file_pointer_reset_to_zero_not_current(self):
        path = self._write_file(b"some data here")
        with open(path, "rb") as f:
            f.read(3)
            sha256sum(f)
            self.assertEqual(f.tell(), 0)


if __name__ == "__main__":
    unittest.main()
