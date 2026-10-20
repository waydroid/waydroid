# Copyright 2026 Waydroid Project
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import threading


class ServiceRunner:
    """
    Run a per-session binder service in a background thread.

    Collapses the lifecycle pattern shared by all per-session services
    (user_manager, clipboard_manager, hardware_manager, notification_manager):
    a stop flag, a worker thread that keeps re-registering the service, and a
    GLib main loop that the binder interface installs on ``args`` (e.g.
    ``args.hardwareLoop``) and that must be quit on stop.
    """

    def __init__(self, name, loop_attr):
        self.name = name
        self.loop_attr = loop_attr
        self._stopping = False
        self._thread = None

    def start(self, run_fn):
        """Run ``run_fn`` repeatedly in a background thread until stopped."""
        self._stopping = False
        self._thread = threading.Thread(target=self._loop, args=(run_fn,))
        self._thread.start()

    def _loop(self, run_fn):
        while not self._stopping:
            run_fn()

    def stop(self, args):
        """Ask the thread to stop and quit the service's GLib main loop."""
        self._stopping = True
        loop = getattr(args, self.loop_attr, None)
        if loop:
            loop.quit()
        else:
            logging.debug("%s service is not even started", self.name)

    def join(self, timeout=None):
        """Wait for the worker thread to finish (no-op if never started)."""
        if self._thread:
            self._thread.join(timeout)
