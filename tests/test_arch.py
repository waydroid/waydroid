# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools.helpers.arch."""

import io
import types

import pytest

import tools.helpers.arch as arch


class FakeOpen:
    """Context manager that fakes reading a file's content."""

    def __init__(self, content):
        self.content = content

    def __call__(self, path, *args, **kwargs):
        return io.StringIO(self.content)


def patch_cpuinfo(monkeypatch, content):
    monkeypatch.setattr("builtins.open", FakeOpen(content))


def test_host_x86_64(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "x86_64")
    patch_cpuinfo(monkeypatch, "ssse3 sse4_2")
    assert arch.host() == "x86_64"


def test_host_x86_64_falls_back_to_x86_without_sse4_2(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "x86_64")
    patch_cpuinfo(monkeypatch, "ssse3")
    assert arch.host() == "x86"


def test_host_x86_64_requires_ssse3(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "x86_64")
    patch_cpuinfo(monkeypatch, "no sse2, no sse3 here")
    with pytest.raises(ValueError):
        arch.host()


def test_host_i686(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "i686")
    patch_cpuinfo(monkeypatch, "ssse3")
    assert arch.host() == "x86"


def test_host_armv7l(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "armv7l")
    assert arch.host() == "arm"


def test_host_armv8l(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "armv8l")
    assert arch.host() == "arm"


def test_host_aarch64(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(arch.platform, "architecture", lambda: ("64bit", "ELF"))
    monkeypatch.setattr(arch, "is_32bit_capable", lambda: True)
    assert arch.host() == "arm64"


def test_host_aarch64_32bit_userspace(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(arch.platform, "architecture", lambda: ("32bit", "ELF"))
    assert arch.host() == "arm"


def test_host_aarch64_without_aarch32(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(arch.platform, "architecture", lambda: ("64bit", "ELF"))
    monkeypatch.setattr(arch, "is_32bit_capable", lambda: False)
    assert arch.host() == "arm64_only"


def test_host_unsupported(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "riscv64")
    with pytest.raises(ValueError):
        arch.host()


def test_is_32bit_capable_true(monkeypatch):
    calls = []

    def fake_personality(arg):
        calls.append(arg)
        return 0  # previous persona (success)

    class FakeLib:
        personality = staticmethod(fake_personality)

    class FakeCDLL:
        def __init__(self, *args, **kwargs):
            self.personality = FakeLib.personality

    fake_ctypes = types.SimpleNamespace(CDLL=FakeCDLL, c_int=int, c_ulong=int)
    monkeypatch.setattr(arch, "ctypes", fake_ctypes)
    assert arch.is_32bit_capable() is True
    # PER_LINUX32 probe, then restore of the previous persona
    assert calls == [0x0008, 0]


def test_is_32bit_capable_false(monkeypatch):
    def fake_personality(arg):
        return -1  # personality() failed

    class FakeLib:
        personality = staticmethod(fake_personality)

    class FakeCDLL:
        def __init__(self, *args, **kwargs):
            self.personality = FakeLib.personality

    fake_ctypes = types.SimpleNamespace(CDLL=FakeCDLL, c_int=int, c_ulong=int)
    monkeypatch.setattr(arch, "ctypes", fake_ctypes)
    assert arch.is_32bit_capable() is False
