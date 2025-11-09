# Copyright 2025 Alessandro Astone
# SPDX-License-Identifier: GPL-3.0-or-later
import tools.config
import dbus

import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

WAYDROID = sys.argv[0]
TARBALL = "waydroid-bugreport.tar.xz"

def logcat(output_path):
    with open(output_path, "w+") as fd:
        return subprocess.Popen(["sudo", WAYDROID, "logcat"], stdout=fd, stderr=sys.stderr, stdin=None)

def dmesg(params, output_path):
    with open(output_path, "w+") as fd:
        return subprocess.Popen(["sudo", "dmesg", "-T"] + params, stdout=fd, stderr=fd, stdin=None)

def waydroid_session(output_path):
    with open(output_path, "w+") as fd:
        return subprocess.Popen([WAYDROID, "session", "start"], stdout=fd, stderr=fd, stdin=None, start_new_session=True)

def clear_line():
    sys.stdout.write("\33[2K\r")

def sleep_progress(seconds):
    bar_length = 50
    time_increment = 0.1
    spinner_chars = ['|', '/', '-', '\\']

    iteration = 0
    time_slept = 0

    try:
        while time_slept < seconds:
            spinner_char = spinner_chars[iteration % len(spinner_chars)]
            filled_length = int(bar_length * time_slept // seconds)
            sys.stdout.write(f"[{'=' * filled_length}{' ' * (bar_length - filled_length)}] {spinner_char}\r")
            sys.stdout.flush()

            time.sleep(time_increment)
            time_slept += time_increment
            iteration += 1
        clear_line()
    except KeyboardInterrupt:
        clear_line()
        print("Interrupted.")


def bugreport(args):
    tmp = tempfile.mkdtemp()

    print("\
The following information will be collected:\n\
  - System kernel logs (kmsg)\n\
  - Android system and user logs (logcat)\n\
  - Waydroid container manager logs (/var/lib/waydroid/waydroid.log)\n\
  - Waydroid configuration files (/var/lib/waydroid/*)\n\
\n\
The information will be stored on your machine.\n\
")

    print("Please authenticate as administrator in order to read system logs.")
    try:
        subprocess.run(["sudo", "-v"])
        print()
    except:
        return

    procs = []
    logfiles = []
    def logfile(name):
        file = os.path.join(tmp, name)
        logfiles.append(file)
        return file

    session = None
    try:
        session = tools.helpers.ipc.DBusContainerService().GetSession()
    except dbus.DBusException:
        pass

    if not session:
        print("Waydroid session not found. Trying to start one...")
        procs.append(waydroid_session(logfile("session.txt")))
        sleep_progress(10)
        try:
            session = tools.helpers.ipc.DBusContainerService().GetSession()
        except dbus.DBusException:
            pass

    if session:
        print("\n\
\033[1mPlease try to reproduce the problem now.\033[0m\n\
Waydroid will collect logs for up to 5 minutes. You may interrupt this operation earlier.\n\
")
        procs.append(logcat(logfile("logcat.txt")))
        procs.append(dmesg(["-w"], logfile("dmesg.txt")))
        sleep_progress(5 * 60)
    else:
        print("Session did not start\n")
        dmesg_process = dmesg([], logfile("dmesg.txt"))

    for p in procs:
        p.terminate()
    for p in procs:
        p.wait()

    print("Creating archive...")

    try:
        with tarfile.open(TARBALL, "w:xz", preset=9) as tar:
            files = [
                "/var/lib/waydroid/waydroid.log",
                "/var/lib/waydroid/waydroid.cfg",
                "/var/lib/waydroid/waydroid_base.prop",
                "/var/lib/waydroid/waydroid.prop",
                "/var/lib/waydroid/lxc",
            ] + logfiles

            for f in files:
                try:
                    tar.add(f, arcname=os.path.basename(f), recursive=True)
                except Exception as e:
                    logging.debug(f"Failed to archive {f}: {repr(e)}")

    except Exception as e:
        raise e
    finally:
        shutil.rmtree(tmp)

    print(f"Created \033[1m{TARBALL}\033[0m")
