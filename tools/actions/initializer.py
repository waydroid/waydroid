# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
import tools.config

import sys
import threading
import multiprocessing
import select
import queue
import time
import dbus
import dbus.service
from gi.repository import GLib

def is_initialized(args):
    return os.path.isfile(args.config) and os.path.isdir(tools.config.defaults["rootfs"])

def get_vendor_type(args):
    vndk_str = helpers.props.host_get(args, "ro.vndk.version")
    ret = "MAINLINE"
    if vndk_str != "":
        vndk = int(vndk_str)
        if vndk > 19:
            ret = "HALIUM_" + str(vndk - 19)

    return ret

def setup_config(args):
    cfg = tools.config.load(args)
    args.arch = helpers.arch.host()
    cfg["waydroid"]["arch"] = args.arch

    preinstalled_images_paths = tools.config.defaults["preinstalled_images_paths"]
    if not args.images_path:
        for preinstalled_images in preinstalled_images_paths:
            if os.path.isdir(preinstalled_images):
                if os.path.isfile(preinstalled_images + "/system.img") and os.path.isfile(preinstalled_images + "/vendor.img"):
                    args.images_path = preinstalled_images
                    break
                else:
                    logging.warning("Found directory {} but missing system or vendor image, ignoring...".format(preinstalled_images))

    if not args.images_path:
        args.images_path = tools.config.defaults["images_path"]
    cfg["waydroid"]["images_path"] = args.images_path

    channels_cfg = tools.config.load_channels()
    device_codename = helpers.props.host_get(args, "ro.product.device")
    args.vendor_type = get_vendor_type(args)

    cfg["waydroid"]["vendor_type"] = args.vendor_type
    helpers.drivers.setupBinderNodes(args)
    cfg["waydroid"]["binder"] = args.BINDER_DRIVER
    cfg["waydroid"]["vndbinder"] = args.VNDBINDER_DRIVER
    cfg["waydroid"]["hwbinder"] = args.HWBINDER_DRIVER
    tools.config.save(args, cfg)

def init(args):
    if not is_initialized(args) or args.force:
        initializer_service = None
        try:
            initializer_service = tools.helpers.ipc.DBusContainerService("/Initializer", "id.waydro.Initializer")
        except dbus.DBusException:
            pass
        setup_config(args)
        status = "STOPPED"
        if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
            status = helpers.lxc.status(args)
        if status != "STOPPED":
            logging.info("Stopping container")
            try:
                container = tools.helpers.ipc.DBusContainerService()
                args.session = container.GetSession()
                container.Stop(False)
            except Exception as e:
                logging.debug(e)
                tools.actions.container_manager.stop(args)
        helpers.images.remove_overlay(args)
        if not os.path.isdir(tools.config.defaults["rootfs"]):
            os.mkdir(tools.config.defaults["rootfs"])
        if not os.path.isdir(tools.config.defaults["overlay"]):
            os.mkdir(tools.config.defaults["overlay"])
            os.mkdir(tools.config.defaults["overlay"]+"/vendor")
        if not os.path.isdir(tools.config.defaults["overlay_rw"]):
            os.mkdir(tools.config.defaults["overlay_rw"])
            os.mkdir(tools.config.defaults["overlay_rw"]+"/system")
            os.mkdir(tools.config.defaults["overlay_rw"]+"/vendor")
        helpers.drivers.probeAshmemDriver(args)
        helpers.lxc.setup_host_perms(args)
        helpers.lxc.set_lxc_config(args)
        helpers.lxc.make_base_props(args)
        if status != "STOPPED":
            logging.info("Starting container")
            try:
                container.Start(args.session)
            except Exception as e:
                logging.debug(e)
                logging.error("Failed to restart container. Please do so manually.")

        if "running_init_in_service" not in args or not args.running_init_in_service:
            try:
                if initializer_service:
                    initializer_service.Done()
            except dbus.DBusException:
                pass
    else:
        logging.info("Already initialized")

def wait_for_init(args):
    helpers.ipc.create_channel("remote_init_output")

    mainloop = GLib.MainLoop()
    dbus_obj = DbusInitializer(mainloop, dbus.SystemBus(), '/Initializer', args)
    mainloop.run()

    # After init
    dbus_obj.remove_from_connection()

class DbusInitializer(dbus.service.Object):
    def __init__(self, looper, bus, object_path, args):
        self.args = args
        self.looper = looper
        dbus.service.Object.__init__(self, bus, object_path)

    @dbus.service.method("id.waydro.Initializer", in_signature='a{ss}', out_signature='', sender_keyword="sender", connection_keyword="conn")
    def Init(self, params, sender=None, conn=None):
        channels_cfg = tools.config.load_channels()
        no_auth = params["system_channel"] == channels_cfg["channels"]["system_channel"] and \
                  params["vendor_channel"] == channels_cfg["channels"]["vendor_channel"]
        if no_auth or ensure_polkit_auth(sender, conn, "id.waydro.Initializer.Init"):
            threading.Thread(target=remote_init_server, args=(self.args, params)).start()
        else:
            raise PermissionError("Polkit: Authentication failed")

    @dbus.service.method("id.waydro.Initializer", in_signature='', out_signature='')
    def Done(self):
        if is_initialized(self.args):
            self.looper.quit()

def ensure_polkit_auth(sender, conn, privilege):
    dbus_info = dbus.Interface(conn.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus/Bus", False), "org.freedesktop.DBus")
    pid = dbus_info.GetConnectionUnixProcessID(sender)
    polkit = dbus.Interface(dbus.SystemBus().get_object("org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority", False), "org.freedesktop.PolicyKit1.Authority")
    try:
        (is_auth, _, _) = polkit.CheckAuthorization(
            ("unix-process", {
                "pid": dbus.UInt32(pid, variant_level=1),
                "start-time": dbus.UInt64(0, variant_level=1)}),
            privilege, {"AllowUserInteraction": "true"},
            dbus.UInt32(1),
            "",
            timeout=300)
        return is_auth
    except dbus.DBusException:
        raise PermissionError("Polkit: Authentication timed out")

def background_remote_init_process(args):
    with helpers.ipc.open_channel("remote_init_output", "wb") as channel_out:
        class StdoutRedirect(logging.StreamHandler):
            def write(self, s):
                channel_out.write(str.encode(s))
            def flush(self):
                pass
            def emit(self, record):
                if record.levelno >= logging.INFO:
                    self.write(self.format(record) + self.terminator)

        out = StdoutRedirect()
        sys.stdout = sys.stderr = out
        logging.getLogger().addHandler(out)

        ctl_queue = queue.Queue()
        def try_init(args):
            try:
                init(args)
            except Exception as e:
                print(str(e))
            finally:
                ctl_queue.put(0)

        def poll_pipe():
            poller = select.poll()
            poller.register(channel_out, select.POLLERR)
            poller.poll()
            # When reaching here the client was terminated
            ctl_queue.put(0)

        init_thread = threading.Thread(target=try_init, args=(args,))
        init_thread.daemon = True
        init_thread.start()

        poll_thread = threading.Thread(target=poll_pipe)
        poll_thread.daemon = True
        poll_thread.start()

        # Join any one of the two threads
        # Then exit the subprocess to kill the remaining thread.
        # Can you believe this is the only way to kill a thread in python???
        ctl_queue.get()

        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        logging.getLogger().removeHandler(out)

def remote_init_server(args, params):
    args.force = True
    args.images_path = ""
    args.rom_type = ""
    args.system_channel = params["system_channel"]
    args.vendor_channel = params["vendor_channel"]
    args.system_type = params["system_type"]
    args.running_init_in_service = True

    p = multiprocessing.Process(target=background_remote_init_process, args=(args,))
    p.daemon = True
    p.start()
    p.join()
