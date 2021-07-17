# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import fcntl
import logging
import selectors
import subprocess
import sys
import threading
import time
import os
import tools.helpers.run

""" For a detailed description of all output modes, read the description of
    core() at the bottom. All other functions in this file get (indirectly)
    called by core(). """


def sanity_checks(output="log", output_return=False, check=None):
    """
    Raise an exception if the parameters passed to core() don't make sense
    (all parameters are described in core() below).
    """
    vals = ["log", "stdout", "interactive", "tui", "background", "pipe"]
    if output not in vals:
        raise RuntimeError("Invalid output value: " + str(output))

    # Prevent setting the check parameter with output="background".
    # The exit code won't be checked when running in background, so it would
    # always by check=False. But we prevent it from getting set to check=False
    # as well, so it does not look like you could change it to check=True.
    if check is not None and output == "background":
        raise RuntimeError("Can't use check with output: background")

    if output_return and output in ["tui", "background"]:
        raise RuntimeError("Can't use output_return with output: " + output)


def background(args, cmd, working_dir=None):
    """ Run a subprocess in background and redirect its output to the log. """
    ret = subprocess.Popen(cmd, stdout=args.logfd, stderr=args.logfd,
                           cwd=working_dir)
    logging.debug("New background process: pid={}, output=background".format(ret.pid))
    return ret


def pipe(args, cmd, working_dir=None):
    """ Run a subprocess in background and redirect its output to a pipe. """
    ret = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=args.logfd,
                           cwd=working_dir)
    logging.verbose("New background process: pid={}, output=pipe".format(ret.pid))
    return ret


def pipe_read(args, process, output_to_stdout=False, output_return=False,
              output_return_buffer=False):
    """
    Read all available output from a subprocess and copy it to the log and
    optionally stdout and a buffer variable. This is only meant to be called by
    foreground_pipe() below.

    :param process: subprocess.Popen instance
    :param output_to_stdout: copy all output to waydroid's stdout
    :param output_return: when set to True, output_return_buffer will be
                          extended
    :param output_return_buffer: list of bytes that gets extended with the
                                 current output in case output_return is True.
    """
    while True:
        # Copy available output
        out = process.stdout.readline()
        if len(out):
            args.logfd.buffer.write(out)
            if output_to_stdout:
                sys.stdout.buffer.write(out)
            if output_return:
                output_return_buffer.append(out)
            continue

        # No more output (flush buffers)
        args.logfd.flush()
        if output_to_stdout:
            sys.stdout.flush()
        return


def kill_process_tree(args, pid, ppids, sudo):
    """
    Recursively kill a pid and its child processes

    :param pid: process id that will be killed
    :param ppids: list of process id and parent process id tuples (pid, ppid)
    :param sudo: use sudo to kill the process
    """
    if sudo:
        tools.helpers.run.root(args, ["kill", "-9", str(pid)],
                             check=False)
    else:
        tools.helpers.run.user(args, ["kill", "-9", str(pid)],
                             check=False)

    for (child_pid, child_ppid) in ppids:
        if child_ppid == str(pid):
            kill_process_tree(args, child_pid, ppids, sudo)


def kill_command(args, pid, sudo):
    """
    Kill a command process and recursively kill its child processes

    :param pid: process id that will be killed
    :param sudo: use sudo to kill the process
    """
    cmd = ["ps", "-e", "-o", "pid,ppid"]
    ret = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    ppids = []
    proc_entries = ret.stdout.decode("utf-8").rstrip().split('\n')[1:]
    for row in proc_entries:
        items = row.split()
        if len(items) != 2:
            raise RuntimeError("Unexpected ps output: " + row)
        ppids.append(items)

    kill_process_tree(args, pid, ppids, sudo)


def foreground_pipe(args, cmd, working_dir=None, output_to_stdout=False,
                    output_return=False, output_timeout=True,
                    sudo=False):
    """
    Run a subprocess in foreground with redirected output and optionally kill
    it after being silent for too long.

    :param cmd: command as list, e.g. ["echo", "string with spaces"]
    :param working_dir: path in host system where the command should run
    :param output_to_stdout: copy all output to waydroid's stdout
    :param output_return: return the output of the whole program
    :param output_timeout: kill the process when it doesn't print any output
                           after a certain time (configured with --timeout)
                           and raise a RuntimeError exception
    :param sudo: use sudo to kill the process when it hits the timeout
    :returns: (code, output)
              * code: return code of the program
              * output: ""
              * output: full program output string (output_return is True)
    """
    # Start process in background (stdout and stderr combined)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=working_dir)

    # Make process.stdout non-blocking
    handle = process.stdout.fileno()
    flags = fcntl.fcntl(handle, fcntl.F_GETFL)
    fcntl.fcntl(handle, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    # While process exists wait for output (with timeout)
    output_buffer = []
    sel = selectors.DefaultSelector()
    sel.register(process.stdout, selectors.EVENT_READ)
    timeout = args.timeout if output_timeout else None
    while process.poll() is None:
        wait_start = time.perf_counter() if output_timeout else None
        sel.select(timeout)

        # On timeout raise error (we need to measure time on our own, because
        # select() may exit early even if there is no data to read and the
        # timeout was not reached.)
        if output_timeout:
            wait_end = time.perf_counter()
            if wait_end - wait_start >= args.timeout:
                logging.info("Process did not write any output for " +
                             str(args.timeout) + " seconds. Killing it.")
                logging.info("NOTE: The timeout can be increased with"
                             " 'waydroid -t'.")
                kill_command(args, process.pid, sudo)
                continue

        # Read all currently available output
        pipe_read(args, process, output_to_stdout, output_return,
                  output_buffer)

    # There may still be output after the process quit
    pipe_read(args, process, output_to_stdout, output_return, output_buffer)

    # Return the return code and output (the output gets built as list of
    # output chunks and combined at the end, this is faster than extending the
    # combined string with each new chunk)
    return (process.returncode, b"".join(output_buffer).decode("utf-8"))


def foreground_tui(cmd, working_dir=None):
    """
    Run a subprocess in foreground without redirecting any of its output.

    This is the only way text-based user interfaces (ncurses programs like
    vim, nano or the kernel's menuconfig) work properly.
    """

    logging.debug("*** output passed to waydroid stdout, not to this log"
                  " ***")
    process = subprocess.Popen(cmd, cwd=working_dir)
    return process.wait()


def check_return_code(args, code, log_message):
    """
    Check the return code of a command.

    :param code: exit code to check
    :param log_message: simplified and more readable form of the command, e.g.
                        "(native) % echo test" instead of the full command with
                        entering the chroot and more escaping
    :raises RuntimeError: when the code indicates that the command failed
    """

    if code:
        logging.debug("^" * 70)
        logging.info("NOTE: The failed command's output is above the ^^^ line"
                     " in the log file: " + args.log)
        raise RuntimeError("Command failed: " + log_message)


def sudo_timer_iterate():
    """
    Run sudo -v and schedule a new timer to repeat the same.
    """

    subprocess.Popen(["sudo", "-v"]).wait()

    timer = threading.Timer(interval=60, function=sudo_timer_iterate)
    timer.daemon = True
    timer.start()


def sudo_timer_start(args):
    """
    Start a timer to call sudo -v periodically, so that the password is only
    needed once.
    """

    if "sudo_timer_active" in args.cache:
        return
    args.cache["sudo_timer_active"] = True

    sudo_timer_iterate()


def core(args, log_message, cmd, working_dir=None, output="log",
         output_return=False, check=None, sudo=False, disable_timeout=False):
    """
    Run a command and create a log entry.

    This is a low level function not meant to be used directly. Use one of the
    following instead: tools.helpers.run.user(), tools.helpers.run.root(),
                       tools.chroot.user(), tools.chroot.root()

    :param log_message: simplified and more readable form of the command, e.g.
                        "(native) % echo test" instead of the full command with
                        entering the chroot and more escaping
    :param cmd: command as list, e.g. ["echo", "string with spaces"]
    :param working_dir: path in host system where the command should run
    :param output: where to write the output (stdout and stderr) of the
                   process. We almost always write to the log file, which can
                   be read with "waydroid log" (output values: "log",
                   "stdout", "interactive", "background"), so it's easy to
                   trace what waydroid does.

                   The exceptions are "tui" (text-based user interface), where
                   it does not make sense to write to the log file (think of
                   ncurses UIs, such as "menuconfig") and "pipe" where the
                   output is written to a pipe for manual asynchronous
                   consumption by the caller.

                   When the output is not set to "interactive", "tui",
                   "background" or "pipe", we kill the process if it does not
                   output anything for 5 minutes (time can be set with
                   "waydroid --timeout").

                   The table below shows all possible values along with
                   their properties. "wait" indicates that we wait for the
                   process to complete.

                   output value  | timeout | out to log | out to stdout | wait
                   -----------------------------------------------------------
                   "log"         | x       | x          |               | x
                   "stdout"      | x       | x          | x             | x
                   "interactive" |         | x          | x             | x
                   "tui"         |         |            | x             | x
                   "background"  |         | x          |               |
                   "pipe"        |         |            |               |

    :param output_return: in addition to writing the program's output to the
                          destinations above in real time, write to a buffer
                          and return it as string when the command has
                          completed. This is not possible when output is
                          "background", "pipe" or "tui".
    :param check: an exception will be raised when the command's return code
                  is not 0. Set this to False to disable the check. This
                  parameter can not be used when the output is "background" or
                  "pipe".
    :param sudo: use sudo to kill the process when it hits the timeout.
    :returns: * program's return code (default)
              * subprocess.Popen instance (output is "background" or "pipe")
              * the program's entire output (output_return is True)
    """
    sanity_checks(output, output_return, check)

    if args.sudo_timer and sudo:
        sudo_timer_start(args)

    # Log simplified and full command (waydroid -v)
    logging.debug(log_message)
    logging.verbose("run: " + str(cmd))

    # Background
    if output == "background":
        return background(args, cmd, working_dir)

    # Pipe
    if output == "pipe":
        return pipe(args, cmd, working_dir)

    # Foreground
    output_after_run = ""
    if output == "tui":
        # Foreground TUI
        code = foreground_tui(cmd, working_dir)
    else:
        # Foreground pipe (always redirects to the error log file)
        output_to_stdout = False
        if not args.details_to_stdout and output in ["stdout", "interactive"]:
            output_to_stdout = True

        output_timeout = output in ["log", "stdout"] and not disable_timeout

        (code, output_after_run) = foreground_pipe(args, cmd, working_dir,
                                                   output_to_stdout,
                                                   output_return,
                                                   output_timeout,
                                                   sudo)

    # Check the return code
    if check is not False:
        check_return_code(args, code, log_message)

    # Return (code or output string)
    return output_after_run if output_return else code
