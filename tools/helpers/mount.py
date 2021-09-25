# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tools.helpers.run


def ismount(folder):
    """
    Ismount() implementation, that works for mount --bind.
    Workaround for: https://bugs.python.org/issue29707
    """
    folder = os.path.realpath(os.path.realpath(folder))
    with open("/proc/mounts", "r") as handle:
        for line in handle:
            words = line.split()
            if len(words) >= 2 and words[1] == folder:
                return True
            if words[0] == folder:
                return True
    return False


def bind(args, source, destination, create_folders=True, umount=False):
    """
    Mount --bind a folder and create necessary directory structure.
    :param umount: when destination is already a mount point, umount it first.
    """
    # Check/umount destination
    if ismount(destination):
        if umount:
            umount_all(args, destination)
        else:
            return

    # Check/create folders
    for path in [source, destination]:
        if os.path.exists(path):
            continue
        if create_folders:
            tools.helpers.run.user(args, ["mkdir", "-p", path])
        else:
            raise RuntimeError("Mount failed, folder does not exist: " +
                               path)

    # Actually mount the folder
    tools.helpers.run.user(args, ["mount", "-o", "bind", source, destination])

    # Verify, that it has worked
    if not ismount(destination):
        raise RuntimeError("Mount failed: " + source + " -> " + destination)


def bind_file(args, source, destination, create_folders=False):
    """
    Mount a file with the --bind option, and create the destination file,
    if necessary.
    """
    # Skip existing mountpoint
    if ismount(destination):
        return

    # Create empty file
    if not os.path.exists(destination):
        if create_folders:
            dir = os.path.dirname(destination)
            if not os.path.isdir(dir):
                tools.helpers.run.user(args, ["mkdir", "-p", dir])

        tools.helpers.run.user(args, ["touch", destination])

    # Mount
    tools.helpers.run.user(args, ["mount", "-o", "bind", source,
                                destination])


def umount_all_list(prefix, source="/proc/mounts"):
    """
    Parses `/proc/mounts` for all folders beginning with a prefix.
    :source: can be changed for testcases
    :returns: a list of folders, that need to be umounted
    """
    ret = []
    prefix = os.path.realpath(prefix)
    with open(source, "r") as handle:
        for line in handle:
            words = line.split()
            if len(words) < 2:
                raise RuntimeError("Failed to parse line in " + source + ": " +
                                   line)
            mountpoint = words[1]
            if mountpoint.startswith(prefix):
                # Remove "\040(deleted)" suffix (#545)
                deleted_str = r"\040(deleted)"
                if mountpoint.endswith(deleted_str):
                    mountpoint = mountpoint[:-len(deleted_str)]
                ret.append(mountpoint)
    ret.sort(reverse=True)
    return ret


def umount_all(args, folder):
    """
    Umount all folders, that are mounted inside a given folder.
    """
    for mountpoint in umount_all_list(folder):
        tools.helpers.run.user(args, ["umount", mountpoint])
        if ismount(mountpoint):
            raise RuntimeError("Failed to umount: " + mountpoint)

def mount(args, source, destination, create_folders=True, umount=False, readonly=True):
    """
    Mount and create necessary directory structure.
    :param umount: when destination is already a mount point, umount it first.
    """
    # Check/umount destination
    if ismount(destination):
        if umount:
            umount_all(args, destination)
        else:
            return

    # Check/create folders
    if not os.path.exists(destination):
        if create_folders:
            tools.helpers.run.user(args, ["mkdir", "-p", destination])
        else:
            raise RuntimeError("Mount failed, folder does not exist: " +
                            destination)

    # Actually mount the folder
    tools.helpers.run.user(args, ["mount", source, destination])
    if readonly:
        tools.helpers.run.user(args, ["mount", "-o", "remount,ro", source, destination])

    # Verify, that it has worked
    if not ismount(destination):
        raise RuntimeError("Mount failed: " + source + " -> " + destination)
