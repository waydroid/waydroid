# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
from shutil import which
import logging
import os
import glob
import signal
import tools.config
from tools import helpers
from tools import services
import dbus
import dbus.service
import dbus.exceptions
from gi.repository import GLib

class DbusContainerManager(dbus.service.Object):
    def __init__(self, looper, bus, object_path, args):
        self.args = args
        self.looper = looper
        dbus.service.Object.__init__(self, bus, object_path)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='a{ss}', out_signature='', sender_keyword="sender", connection_keyword="conn")
    def Start(self, session, sender, conn):
        dbus_info = dbus.Interface(conn.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus/Bus", False), "org.freedesktop.DBus")
        uid = dbus_info.GetConnectionUnixUser(sender)
        if str(uid) not in ["0", session["user_id"]]:
            raise RuntimeError("Cannot start a session on behalf of another user")
        pid = dbus_info.GetConnectionUnixProcessID(sender)
        if str(uid) != "0" and str(pid) != session["pid"]:
            raise RuntimeError("Invalid session pid")
        do_start(self.args, session)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='b', out_signature='')
    def Stop(self, quit_session):
        stop(self.args, quit_session)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='')
    def Freeze(self):
        freeze(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='')
    def Unfreeze(self):
        unfreeze(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='a{ss}')
    def GetSession(self):
        try:
            session = self.args.session
            session["state"] = helpers.lxc.status(self.args)
            return session
        except AttributeError:
            return {}

def service(args, looper):
    dbus_obj = DbusContainerManager(looper, dbus.SystemBus(), '/ContainerManager', args)
    looper.run()

def set_permissions(args, perm_list=None, mode="777"):
    def chmod(path, mode):
        if os.path.exists(path):
            command = ["chmod", mode, "-R", path]
            tools.helpers.run.user(args, command, check=False)

    # Nodes list
    if not perm_list:
        perm_list = [
            "/dev/ashmem",

            # sw_sync for HWC
            "/dev/sw_sync",
            "/sys/kernel/debug/sync/sw_sync",

            # Media
            "/dev/Vcodec",
            "/dev/MTK_SMI",
            "/dev/mdp_sync",
            "/dev/mtk_cmdq",

            # Graphics
            "/dev/graphics",
            "/dev/pvr_sync",
            "/dev/ion",
        ]

        # DRM render nodes
        perm_list.extend(glob.glob("/dev/dri/renderD*"))
        # Framebuffers
        perm_list.extend(glob.glob("/dev/fb*"))
        # Videos
        perm_list.extend(glob.glob("/dev/video*"))
        # DMA-BUF Heaps
        perm_list.extend(glob.glob("/dev/dma_heap/*"))

    for path in perm_list:
        chmod(path, mode)

def start(args):
    try:
        name = dbus.service.BusName("id.waydro.Container", dbus.SystemBus(), do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        logging.error("Container service is already running")
        return

    status = helpers.lxc.status(args)
    if status == "STOPPED":
        # Load binder and ashmem drivers
        cfg = tools.config.load(args)
        if cfg["waydroid"]["vendor_type"] == "MAINLINE":
            if helpers.drivers.probeBinderDriver(args) != 0:
                logging.error("Failed to load Binder driver")
            helpers.drivers.probeAshmemDriver(args)
        helpers.drivers.loadBinderNodes(args)
        set_permissions(args, [
            "/dev/" + args.BINDER_DRIVER,
            "/dev/" + args.VNDBINDER_DRIVER,
            "/dev/" + args.HWBINDER_DRIVER
        ], "666")

        mainloop = GLib.MainLoop()

        def sigint_handler(data):
            stop(args)
            mainloop.quit()

        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, sigint_handler, None)
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, sigint_handler, None)
        service(args, mainloop)
    else:
        logging.error("WayDroid container is {}".format(status))

def do_start(args, session):
    if "session" in args:
        raise RuntimeError("Already tracking a session")

    # Networking
    command = [tools.config.tools_src +
               "/data/scripts/waydroid-net.sh", "start"]
    tools.helpers.run.user(args, command)

    # Sensors
    if which("waydroid-sensord"):
        tools.helpers.run.user(
            args, ["waydroid-sensord", "/dev/" + args.HWBINDER_DRIVER], output="background")

    # Cgroup hacks
    if which("start"):
        command = ["start", "cgroup-lite"]
        tools.helpers.run.user(args, command, check=False)

    # Keep schedtune around in case nesting is supported
    if os.path.ismount("/sys/fs/cgroup/schedtune"):
        try:
            os.mkdir("/sys/fs/cgroup/schedtune/probe0")
            os.mkdir("/sys/fs/cgroup/schedtune/probe0/probe1")
        except:
            command = ["umount", "-l", "/sys/fs/cgroup/schedtune"]
            tools.helpers.run.user(args, command, check=False)
        finally:
            if os.path.exists("/sys/fs/cgroup/schedtune/probe0/probe1"):
                os.rmdir("/sys/fs/cgroup/schedtune/probe0/probe1")
            if os.path.exists("/sys/fs/cgroup/schedtune/probe0"):
                os.rmdir("/sys/fs/cgroup/schedtune/probe0")

    #TODO: remove NFC hacks
    if which("stop"):
        command = ["stop", "nfcd"]
        tools.helpers.run.user(args, command, check=False)
    elif which("systemctl") and (tools.helpers.run.user(args, ["systemctl", "is-active", "-q", "nfcd"], check=False) == 0):
        command = ["systemctl", "stop", "nfcd"]
        tools.helpers.run.user(args, command, check=False)

    # Set permissions
    set_permissions(args)

    # Create session-specific LXC config file
    helpers.lxc.generate_session_lxc_config(args, session)
    # Backwards compatibility
    with open(tools.config.defaults["lxc"] + "/waydroid/config") as f:
        if "config_session" not in f.read():
            helpers.mount.bind(args, session["waydroid_data"],
                               tools.config.defaults["data"])

    # Mount rootfs
    cfg = tools.config.load(args)
    helpers.images.mount_rootfs(args, cfg["waydroid"]["images_path"], session)

    helpers.protocol.set_aidl_version(args)

    helpers.lxc.start(args)
    services.hardware_manager.start(args)

    args.session = session

def stop(args, quit_session=True):
    try:
        services.hardware_manager.stop(args)
        status = helpers.lxc.status(args)
        if status != "STOPPED":
            helpers.lxc.stop(args)
            while helpers.lxc.status(args) != "STOPPED":
                pass

        # Networking
        command = [tools.config.tools_src +
                   "/data/scripts/waydroid-net.sh", "stop"]
        tools.helpers.run.user(args, command, check=False)

        #TODO: remove NFC hacks
        if which("start"):
            command = ["start", "nfcd"]
            tools.helpers.run.user(args, command, check=False)
        elif which("systemctl") and (tools.helpers.run.user(args, ["systemctl", "is-enabled", "-q", "nfcd"], check=False) == 0):
            command = ["systemctl", "start", "nfcd"]
            tools.helpers.run.user(args, command, check=False)

        # Sensors
        if which("waydroid-sensord"):
            command = ["pidof", "waydroid-sensord"]
            pid = tools.helpers.run.user(args, command, check=False, output_return=True).strip()
            if pid:
                command = ["kill", "-9", pid]
                tools.helpers.run.user(args, command, check=False)

        # Umount rootfs
        helpers.images.umount_rootfs(args)

        # Backwards compatibility
        try:
            helpers.mount.umount_all(args, tools.config.defaults["data"])
        except:
            pass

        if "session" in args:
            if quit_session:
                try:
                    os.kill(int(args.session["pid"]), signal.SIGUSR1)
                except:
                    pass
            del args.session
    except:
        pass

def restart(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.stop(args)
        helpers.lxc.start(args)
    else:
        logging.error("WayDroid container is {}".format(status))

def freeze(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.freeze(args)
        while helpers.lxc.status(args) == "RUNNING":
            pass
    else:
        logging.error("WayDroid container is {}".format(status))

def unfreeze(args):
    status = helpers.lxc.status(args)
    if status == "FROZEN":
        helpers.lxc.unfreeze(args)
        while helpers.lxc.status(args) == "FROZEN":
            pass
