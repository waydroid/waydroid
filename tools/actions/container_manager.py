# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
from shutil import which
import logging
import os
import time
import glob
import signal
import sys
import uuid
import threading
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

    @dbus.service.method(dbus_interface='org.freedesktop.DBus.Properties', in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name != "id.waydro.ContainerManager":
            return {}

        session = self.GetSession()
        # Convert each string value to variant
        return dict((k, dbus.String(v, variant_level=1)) for k, v in session.items())

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

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='')
    def Screen(self):
        screen(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='b')
    def isAsleep(self):
        return is_asleep(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='b')
    def OpenAppPresent(self):
        return open_app_present(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='a{ss}')
    def GetSession(self):
        try:
            session = self.args.session
            session["state"] = helpers.lxc.status(self.args)
            return session
        except AttributeError:
            return {}

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='')
    def InstallBaseApk(self):
        install_base_apk(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='s', out_signature='')
    def RemoveApp(self, packageName):
        remove_app(self.args, packageName)

    @dbus.service.method("id.waydro.ContainerManager", out_signature='')
    def MountSharedFolder(self):
        guest_dir = self.args.session['waydroid_data'] + '/media/0/Host'
        host_dir = self.args.session['host_user'] + '/Android'
        helpers.mount.bind(self.args, guest_dir, host_dir)
        chmod(self.args, host_dir, "777")

    @dbus.service.method("id.waydro.ContainerManager", out_signature='')
    def UnmountSharedFolder(self):
        host_dir = self.args.session['host_user'] + '/Android'
        if helpers.mount.ismount(host_dir):
            helpers.mount.umount_all(self.args, host_dir)
            os.rmdir(host_dir)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='')
    def NfcToggle(self):
        nfc_toggle(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='b')
    def GetNfcStatus(self):
        return nfc_status(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='', out_signature='')
    def ForceFinishSetup(self):
        force_finish_setup(self.args)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='s', out_signature='')
    def ClearAppData(self, packageName):
        clear_app_data(self.args, packageName)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='s', out_signature='')
    def KillApp(self, packageName):
        kill_app(self.args, packageName)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='s', out_signature='')
    def KillPid(self, pid):
        kill_pid(self.args, pid)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='ss', out_signature='')
    def Setprop(self, propname, propvalue):
        setprop(self.args, propname, propvalue)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='s', out_signature='s')
    def Getprop(self, propname):
        return getprop(self.args, propname)

    @dbus.service.method("id.waydro.ContainerManager", in_signature='s', out_signature='s', async_callbacks=('reply_handler', 'error_handler'))
    def WatchProp(self, propname, reply_handler, error_handler):
        """
        Asynchronously handles a long-running or blocking watch_prop call
        without blocking the main loop.
        """

        def worker():
            try:
                result = watch_prop(self.args, propname)
                reply_handler(result)
            except Exception as e:
                logging.exception("Error in WatchProp thread")
                error_handler(str(e))

        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

def service(args, looper):
    dbus_obj = DbusContainerManager(looper, dbus.SystemBus(), '/ContainerManager', args)
    looper.run()

def chmod(args, path, mode):
    if os.path.exists(path):
        command = ["chmod", mode, "-R", path]
        tools.helpers.run.user(args, command, check=False)

def set_permissions(args, perm_list=None, mode="777"):
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
            "/dev/mtk_mdp",

            # Graphics
            "/dev/dri",
            "/dev/graphics",
            "/dev/pvr_sync",
            "/dev/ion",
        ]

        # Framebuffers
        perm_list.extend(glob.glob("/dev/fb*"))
        # Videos
        perm_list.extend(glob.glob("/dev/video*"))

    for path in perm_list:
        chmod(args, path, mode)

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

    # Cgroup hacks
    if os.path.ismount("/sys/fs/cgroup/schedtune"):
        command = ["umount", "-l", "/sys/fs/cgroup/schedtune"]
        tools.helpers.run.user(args, command, check=False)

    #TODO: remove NFC hacks
    if which("systemctl") and (tools.helpers.run.user(args, ["systemctl", "is-active", "-q", "nfcd"], check=False) == 0):
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

    args.session = session

def stop(args, quit_session=True):
    try:
        status = helpers.lxc.status(args)
        if status != "STOPPED":
            helpers.lxc.stop(args)
            while helpers.lxc.status(args) != "STOPPED":
                pass

        # Networking
        command = [tools.config.tools_src +
                   "/data/scripts/waydroid-net.sh", "stop"]
        tools.helpers.run.user(args, command, check=False)

        # Umount rootfs
        helpers.images.umount_rootfs(args)

        # Backwards compatibility
        try:
            helpers.mount.umount_all(args, tools.config.defaults["data"])
        except:
            pass

        if which("systemctl") and (tools.helpers.run.user(args, ["systemctl", "is-enabled", "-q", "nfcd"], check=False) == 0):
            command = ["systemctl", "start", "nfcd"]
            tools.helpers.run.user(args, command, check=False)

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

def screen(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.screen_toggle(args)

def is_asleep(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.sleep_status()

def open_app_present(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.open_app_present()

def install_base_apk(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.install_base_apk(args)

def remove_app(args, packageName):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.remove_app(args, packageName)

def nfc_toggle(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.toggle_nfc(args)

def nfc_status(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.nfc_status()

def force_finish_setup(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.force_finish_setup(args)

def clear_app_data(args, packageName):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.clear_app_data(args, packageName)

def kill_app(args, packageName):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.kill_app(args, packageName)

def kill_pid(args, pid):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.kill_pid(args, pid)

def setprop(args, propname, propvalue):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.setprop(args, propname, propvalue)

def getprop(args, propname):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.getprop(propname)

def watch_prop(args, propname):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        return helpers.lxc.watch_prop(propname)
