# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from tools import helpers
import tools.config
import pathlib
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
            halium_ver = vndk - 19
            if vndk > 31:
                halium_ver -= 1 # 12L -> Halium 12
            ret = "HALIUM_" + str(halium_ver)
            if vndk == 32:
                ret += "L"

    return ret

def setup_config(args):
    cfg = tools.config.load(args)
    args.arch = helpers.arch.host()
    cfg["waydroid"]["arch"] = args.arch

    args.vendor_type = get_vendor_type(args)
    cfg["waydroid"]["vendor_type"] = args.vendor_type

    helpers.drivers.setupBinderNodes(args)
    cfg["waydroid"]["binder"] = args.BINDER_DRIVER
    cfg["waydroid"]["vndbinder"] = args.VNDBINDER_DRIVER
    cfg["waydroid"]["hwbinder"] = args.HWBINDER_DRIVER

    has_preinstalled_images = False
    preinstalled_images_paths = tools.config.defaults["preinstalled_images_paths"]
    for preinstalled_images in preinstalled_images_paths:
        if os.path.isdir(preinstalled_images):
            system_path = preinstalled_images + "/system.img"
            vendor_path = preinstalled_images + "/vendor.img"
            are_files = os.path.isfile(system_path) and os.path.isfile(vendor_path)
            are_links = pathlib.Path.is_block_device(system_path) and pathlib.Path.is_block_device(vendor_path)
            if are_files or are_links:
                has_preinstalled_images = True
                args.images_path = preinstalled_images
                break
            else:
                logging.warning("Found directory {} but missing system or vendor image, ignoring...".format(preinstalled_images))

    if not args.images_path:
        args.images_path = tools.config.defaults["images_path"]
    cfg["waydroid"]["images_path"] = args.images_path

    if has_preinstalled_images:
        cfg["waydroid"]["system_ota"] = args.system_ota = "None"
        cfg["waydroid"]["vendor_ota"] = args.vendor_ota = "None"
        cfg["waydroid"]["system_datetime"] = tools.config.defaults["system_datetime"]
        cfg["waydroid"]["vendor_datetime"] = tools.config.defaults["vendor_datetime"]
        tools.config.save(args, cfg)
        return True

    channels_cfg = tools.config.load_channels()
    if not args.system_channel:
        args.system_channel = channels_cfg["channels"]["system_channel"]
    if not args.vendor_channel:
        args.vendor_channel = channels_cfg["channels"]["vendor_channel"]
    if not args.rom_type:
        args.rom_type = channels_cfg["channels"]["rom_type"]
    if not args.system_type:
        args.system_type = channels_cfg["channels"]["system_type"]

    if not args.system_channel or not args.vendor_channel:
        logging.error("ERROR: You must provide 'System OTA' and 'Vendor OTA' URLs.")
        return False

    args.system_ota = args.system_channel + "/" + args.rom_type + \
        "/waydroid_" + args.arch + "/" + args.system_type + ".json"
    system_request = helpers.http.retrieve(args.system_ota)
    if system_request[0] != 200:
        raise ValueError(
            "Failed to get system OTA channel: {}, error: {}".format(args.system_ota, system_request[0]))

    device_codename = helpers.props.host_get(args, "ro.product.device")
    args.vendor_type = None
    for vendor in [device_codename, get_vendor_type(args)]:
        vendor_ota = args.vendor_channel + "/waydroid_" + \
            args.arch + "/" + vendor.replace(" ", "_") + ".json"
        vendor_request = helpers.http.retrieve(vendor_ota)
        if vendor_request[0] == 200:
            args.vendor_type = vendor
            args.vendor_ota = vendor_ota
            break

    if not args.vendor_type:
        raise ValueError(
            "Failed to get vendor OTA channel: {}".format(vendor_ota))

    if args.system_ota != cfg["waydroid"].get("system_ota"):
        cfg["waydroid"]["system_datetime"] = tools.config.defaults["system_datetime"]
    if args.vendor_ota != cfg["waydroid"].get("vendor_ota"):
        cfg["waydroid"]["vendor_datetime"] = tools.config.defaults["vendor_datetime"]

    cfg["waydroid"]["vendor_type"] = args.vendor_type
    cfg["waydroid"]["system_ota"] = args.system_ota
    cfg["waydroid"]["vendor_ota"] = args.vendor_ota
    tools.config.save(args, cfg)
    return True

def init(args):
    if is_initialized(args) and not args.force:
        logging.info("Already initialized")

    if not setup_config(args):
        return

    status = "STOPPED"
    session = None
    if os.path.exists(tools.config.defaults["lxc"] + "/waydroid"):
        status = helpers.lxc.status(args)
    if status != "STOPPED":
        if "running_init_in_service" in args:
            session = args.session
            tools.actions.container_manager.stop(args, False)
        else:
            logging.info("Stopping container")
            try:
                container = tools.helpers.ipc.DBusContainerService()
                session = container.GetSession()
                container.Stop(False)
            except Exception as e:
                logging.debug(e)
                tools.actions.container_manager.stop(args, False)
    if args.images_path not in tools.config.defaults["preinstalled_images_paths"]:
        helpers.images.get(args)
    else:
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
        try:
            if "running_init_in_service" in args:
                tools.actions.container_manager.do_start(args, session)
            else:
                logging.info("Starting container")
                container.Start(session)
        except Exception as e:
            logging.debug(e)
            logging.error("Failed to restart container. Please do so manually.")

class DbusInitializer(dbus.service.Object):
    def __init__(self, looper, bus, object_path, args):
        self.args = args
        self.looper = looper
        self.worker_thread = None
        dbus.service.Object.__init__(self, bus, object_path)

    @helpers.logging.log_exceptions
    @dbus.service.method("id.waydro.Initializer", in_signature='a{ss}', out_signature='', sender_keyword="sender", connection_keyword="conn")
    def Init(self, params, sender=None, conn=None):
        if self.worker_thread is not None:
            self.worker_thread.kill()
            self.worker_thread.join()

        channels_cfg = tools.config.load_channels()
        no_auth = params["system_channel"] == channels_cfg["channels"]["system_channel"] and \
                  params["vendor_channel"] == channels_cfg["channels"]["vendor_channel"]
        if no_auth or ensure_polkit_auth(sender, conn, "id.waydro.Initializer.Init"):
            self.worker_thread = remote_init_server(self.args, self, params)
        else:
            raise PermissionError("Polkit: Authentication failed")

    @helpers.logging.log_exceptions
    @dbus.service.method("id.waydro.Initializer", in_signature='', out_signature='')
    def Cancel(self):
        if self.worker_thread is not None:
            self.worker_thread.kill()
            self.worker_thread.join()

    @dbus.service.signal("id.waydro.Initializer", signature='s')
    def ProgressChanged(self, message):
        pass

    @dbus.service.signal("id.waydro.Initializer", signature='')
    def Finished(self):
        pass

    @dbus.service.signal("id.waydro.Initializer", signature='')
    def Interrupted(self):
        pass

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

def remote_init_server(args, dbus_obj, params):
    args.force = True
    args.images_path = ""
    args.rom_type = ""
    args.system_channel = params["system_channel"]
    args.vendor_channel = params["vendor_channel"]
    args.system_type = params["system_type"]
    args.running_init_in_service = True

    class StdoutRedirect(logging.StreamHandler):
        def __init__(self, pipe):
            logging.StreamHandler.__init__(self)
            self.pipe = pipe
        def write(self, s):
            self.pipe.send(s)
        def flush(self):
            pass
        def emit(self, record):
            if record.levelno >= logging.INFO:
                self.write(self.format(record) + self.terminator)

    def init_proc(args, pipe):
        out = StdoutRedirect(pipe)
        sys.stdout = sys.stderr = out
        logging.getLogger().addHandler(out)

        try:
            init(args)
            sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(1)
        except Exception as e:
            logging.exception("Exception during init")
            sys.exit(1)
        finally:
            pipe.close()

    parent_conn, child_conn = multiprocessing.Pipe(False)
    p = multiprocessing.Process(target=init_proc, args=(args, child_conn,), daemon=True)
    p.start()

    def monitor_init(p, pipe):
        try:
            while True:
                dbus_obj.ProgressChanged(pipe.recv())
        except EOFError:
            pass

        p.join()
        if p.exitcode == 0:
            GLib.idle_add(dbus_obj.Finished)
        else:
            GLib.idle_add(dbus_obj.Interrupted)

    t = threading.Thread(target=monitor_init, args=(p, parent_conn,), daemon=True)
    t.kill = lambda: p.kill()
    t.start()
    return t


def remote_init_client(args):
    # Local imports cause Gtk is intrusive
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    class WaydroidInitWindow(Gtk.Window):
        def __init__(self):
            super().__init__(title="Initialize Waydroid")
            channels_cfg = tools.config.load_channels()

            self.set_default_size(600, 250)
            self.set_icon_name("waydroid")

            grid = Gtk.Grid(row_spacing=6, column_spacing=6, margin=10, column_homogeneous=True)
            grid.set_hexpand(True)
            grid.set_vexpand(True)
            self.add(grid)

            sysOtaLabel = Gtk.Label("System OTA")
            sysOtaEntry = Gtk.Entry()
            sysOtaEntry.set_text(channels_cfg["channels"]["system_channel"])
            grid.attach(sysOtaLabel, 0, 0, 1, 1)
            grid.attach_next_to(sysOtaEntry ,sysOtaLabel, Gtk.PositionType.RIGHT, 2, 1)
            self.sysOta = sysOtaEntry.get_buffer()

            vndOtaLabel = Gtk.Label("Vendor OTA")
            vndOtaEntry = Gtk.Entry()
            vndOtaEntry.set_text(channels_cfg["channels"]["vendor_channel"])
            grid.attach(vndOtaLabel, 0, 1, 1, 1)
            grid.attach_next_to(vndOtaEntry, vndOtaLabel, Gtk.PositionType.RIGHT, 2, 1)
            self.vndOta = vndOtaEntry.get_buffer()

            sysTypeLabel = Gtk.Label("Android Type")
            sysTypesStore = Gtk.ListStore(str, str)
            sysTypesStore.append(["VANILLA", "Minimal Android"])
            sysTypesStore.append(["GAPPS", "Android with Google Apps"])

            sysTypeCombo = Gtk.ComboBox.new_with_model(sysTypesStore)
            renderer_text = Gtk.CellRendererText()
            sysTypeCombo.pack_start(renderer_text, True)
            sysTypeCombo.add_attribute(renderer_text, "text", 1)
            sysTypeCombo.set_active(0)
            grid.attach(sysTypeLabel, 0, 2, 1, 1)
            grid.attach_next_to(sysTypeCombo, sysTypeLabel, Gtk.PositionType.RIGHT, 2, 1)
            self.sysType = sysTypeCombo

            downloadBtn = Gtk.Button("Download")
            downloadBtn.connect("clicked", self.on_download_btn_clicked)
            grid.attach(downloadBtn, 1,3,1,1)
            self.downloadBtn = downloadBtn

            doneBtn = Gtk.Button("Done")
            doneBtn.connect("clicked", lambda x: self.destroy())
            doneBtn.get_style_context().add_class('suggested-action')
            grid.attach_next_to(doneBtn, downloadBtn, Gtk.PositionType.RIGHT, 1, 1)
            self.doneBtn = doneBtn

            outScrolledWindow = Gtk.ScrolledWindow()
            outScrolledWindow.set_hexpand(True)
            outScrolledWindow.set_vexpand(True)
            outTextView = Gtk.TextView()
            outTextView.set_property('editable', False)
            outTextView.set_property('cursor-visible', False)
            outScrolledWindow.add(outTextView)
            grid.attach(outScrolledWindow, 0, 4, 3, 1)
            self.outScrolledWindow = outScrolledWindow
            self.outTextView = outTextView
            self.outBuffer = outTextView.get_buffer()
            self.outBuffer.create_mark("end", self.outBuffer.get_end_iter(), False)

            self.bus_signals = []
            self.initializing = False

            self.connect("destroy", self.on_destroy)

        def scroll_to_bottom(self):
            self.outTextView.scroll_mark_onscreen(self.outBuffer.get_mark("end"))

        def on_download_btn_clicked(self, widget):
            widget.set_sensitive(False)
            self.doneBtn.hide()
            self.outTextView.show()
            sysType = self.sysType.get_model()[self.sysType.get_active_iter()][0]
            self.run_init(self.sysOta.get_text(), self.vndOta.get_text(), sysType)

        def draw(self, s):
            if s.startswith('\r'):
                last = self.outBuffer.get_iter_at_line(self.outBuffer.get_line_count()-1)
                last.backward_char()
                self.outBuffer.delete(last, self.outBuffer.get_end_iter())
            self.outBuffer.insert(self.outBuffer.get_end_iter(), s)
            self.scroll_to_bottom()

        def on_progress(self, message):
            self.draw(message)

        def on_finished(self):
            self.initializing = False
            if is_initialized(args):
                self.doneBtn.show()
                self.draw("\nDone\n")

        def on_interrupted(self):
            self.initializing = False
            self.draw("\nInterrupted\n")

        def on_reply(self):
            self.downloadBtn.set_sensitive(True)

        def on_bus_error(self, e):
            if e.get_dbus_name() == "org.freedesktop.DBus.Python.PermissionError":
                self.draw(e.get_dbus_message().splitlines()[-1] + "\n")
            else:
                self.draw(str(e))
            self.downloadBtn.set_sensitive(True)

        def on_destroy(self, _):
            if self.initializing:
                try:
                    tools.helpers.ipc.DBusContainerService("/Initializer", "id.waydro.Initializer").Cancel()
                except:
                    pass
            Gtk.main_quit()

        def run_init(self, systemOta, vendorOta, systemType):
            for signal in self.bus_signals:
                signal.remove()

            self.draw("\nWaiting for waydroid container service...\n")
            self.bus_signals = []
            self.initializing = True

            try:
                initializer = tools.helpers.ipc.DBusContainerService("/Initializer", "id.waydro.Initializer")

                self.bus_signals.append(initializer.connect_to_signal("ProgressChanged", self.on_progress))
                self.bus_signals.append(initializer.connect_to_signal("Finished", self.on_finished))
                self.bus_signals.append(initializer.connect_to_signal("Interrupted", self.on_interrupted))

                params = {
                    "system_channel": systemOta,
                    "vendor_channel": vendorOta,
                    "system_type": systemType
                }
                initializer.Init(params, reply_handler=self.on_reply, error_handler=self.on_bus_error)
            except dbus.DBusException as e:
                self.on_bus_error(e)
            except Exception as e:
                self.draw(f"{e}\n")

    GLib.set_prgname("Waydroid")
    win = WaydroidInitWindow()

    win.show_all()
    win.outTextView.hide()
    win.doneBtn.hide()

    Gtk.main()
