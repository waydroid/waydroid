# SPDX-License-Identifier: GPL-3.0-or-later
import time

from tools.services.runner import ServiceRunner


class _Args:
    pass


class _Loop:
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


def test_start_runs_until_stopped():
    calls = []

    def run_fn():
        calls.append(1)
        time.sleep(0.01)

    args = _Args()
    runner = ServiceRunner("Test", "testLoop")
    runner.start(run_fn)
    time.sleep(0.05)
    assert len(calls) >= 2

    runner.stop(args)
    runner.join()
    count_at_stop = len(calls)
    time.sleep(0.03)
    assert len(calls) == count_at_stop


def test_stop_quits_glib_loop():
    args = _Args()
    args.testLoop = _Loop()
    runner = ServiceRunner("Test", "testLoop")

    runner.stop(args)

    assert args.testLoop.quit_called


def test_stop_when_never_started_is_quiet(caplog):
    import logging
    runner = ServiceRunner("Test", "testLoop")

    with caplog.at_level(logging.DEBUG):
        runner.stop(_Args())

    assert any("not even started" in record.message for record in caplog.records)


def test_session_stop_quits_all_service_loops(monkeypatch):
    # The session stop path must quit the GLib loop of every per-session
    # service (user/clipboard/notification) plus the session main loop.
    import types

    import tools.actions.session_manager as session_manager

    loops = {name: _Loop() for name in
             ("userMonitorLoop", "clipboardLoop", "notificationLoop")}
    args = types.SimpleNamespace(**loops)
    mainloop = _Loop()

    session_manager.do_stop(args, mainloop)

    for loop in loops.values():
        assert loop.quit_called
    assert mainloop.quit_called


def test_join_returns_after_stop():
    runner = ServiceRunner("Test", "testLoop")
    runner.start(lambda: None)
    runner.stop(_Args())
    # Should not hang or raise
    runner.join(timeout=2)
