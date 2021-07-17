# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import shlex
import tools.helpers.run_core


def flat_cmd(cmd, working_dir=None, env={}):
    """
    Convert a shell command passed as list into a flat shell string with
    proper escaping.

    :param cmd: command as list, e.g. ["echo", "string with spaces"]
    :param working_dir: when set, prepend "cd ...;" to execute the command
                        in the given working directory
    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}
    :returns: the flat string, e.g.
              echo 'string with spaces'
              cd /home/pmos;echo 'string with spaces'
    """
    # Merge env and cmd into escaped list
    escaped = []
    for key, value in env.items():
        escaped.append(key + "=" + shlex.quote(value))
    for i in range(len(cmd)):
        escaped.append(shlex.quote(cmd[i]))

    # Prepend working dir
    ret = " ".join(escaped)
    if working_dir:
        ret = "cd " + shlex.quote(working_dir) + ";" + ret

    return ret


def user(args, cmd, working_dir=None, output="log", output_return=False,
         check=None, env={}, sudo=False):
    """
    Run a command on the host system as user.

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}

    See tools.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    # Readable log message (without all the escaping)
    msg = "% "
    for key, value in env.items():
        msg += key + "=" + value + " "
    if working_dir:
        msg += "cd " + working_dir + "; "
    msg += " ".join(cmd)

    # Add environment variables and run
    if env:
        cmd = ["sh", "-c", flat_cmd(cmd, env=env)]
    return tools.helpers.run_core.core(args, msg, cmd, working_dir, output,
                                     output_return, check, sudo)


def root(args, cmd, working_dir=None, output="log", output_return=False,
         check=None, env={}):
    """
    Run a command on the host system as root, with sudo.

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}

    See tools.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    if env:
        cmd = ["sh", "-c", flat_cmd(cmd, env=env)]
    cmd = ["sudo"] + cmd

    return user(args, cmd, working_dir, output, output_return, check, env,
                True)
