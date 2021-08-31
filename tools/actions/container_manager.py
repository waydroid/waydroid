# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
from shutil import which
import logging
import os
import time
import glob
import signal
import sys
import tools.config
from tools import helpers
from tools import services


def start(args):
    def make_prop(full_props_path):
        def add_prop(key, cfg_key):
            value = session_cfg["session"][cfg_key]
            if value != "None":
                props.append(key + "=" + session_cfg["session"][cfg_key])

        if not os.path.isfile(args.work + "/waydroid_base.prop"):
            raise RuntimeError("waydroid_base.prop Not found")
        with open(args.work + "/waydroid_base.prop") as f:
            props = f.read().splitlines()
        if not props:
            raise RuntimeError("waydroid_base.prop is broken!!?")

        add_prop("waydroid.host.user", "user_name")
        add_prop("waydroid.host.uid", "user_id")
        add_prop("waydroid.host.gid", "group_id")
        add_prop("waydroid.xdg_runtime_dir", "xdg_runtime_dir")
        add_prop("waydroid.pulse_runtime_path", "pulse_runtime_path")
        add_prop("waydroid.wayland_display", "wayland_display")
        if which("waydroid-sensord") is None:
            props.append("waydroid.stub_sensors_hal=1")
        dpi = session_cfg["session"]["lcd_density"]
        if dpi != "0":
            props.append("ro.sf.lcd_density=" + dpi)

        final_props = open(full_props_path, "w")
        for prop in props:
            final_props.write(prop + "\n")
        final_props.close()
        os.chmod(full_props_path, 0o644)

    def set_permissions(perm_list=None, mode="777"):
        def chmod(path, mode):
            if os.path.exists(path):
                command = ["chmod", mode, "-R", path]
                tools.helpers.run.root(args, command, check=False)

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
                "/dev/video32",
                "/dev/video33",

                # Graphics
                "/dev/dri",
                "/dev/graphics",

                # Wayland and pulse socket permissions
                session_cfg["session"]["pulse_runtime_path"],
                session_cfg["session"]["xdg_runtime_dir"]
            ]

            # Framebuffers
            perm_list.extend(glob.glob("/dev/fb*"))

        for path in perm_list:
            chmod(path, mode)

    def signal_handler(sig, frame):
        services.hardware_manager.stop(args)
        stop(args)
        sys.exit(0)

    status = helpers.lxc.status(args)
    if status == "STOPPED":
        # Load binder and ashmem drivers
        cfg = tools.config.load(args)
        if cfg["waydroid"]["vendor_type"] == "MAINLINE":
            if helpers.drivers.probeBinderDriver(args) != 0:
                logging.error("Failed to load Binder driver")
            if helpers.drivers.probeAshmemDriver(args) != 0:
                logging.error("Failed to load Ashmem driver")
        helpers.drivers.loadBinderNodes(args)
        set_permissions([
            "/dev/" + args.BINDER_DRIVER,
            "/dev/" + args.VNDBINDER_DRIVER,
            "/dev/" + args.HWBINDER_DRIVER
        ], "666")

        if os.path.exists(tools.config.session_defaults["config_path"]):
            session_cfg = tools.config.load_session()
            if session_cfg["session"]["state"] != "STOPPED":
                logging.warning("Found session config on state: {}, restart session".format(
                    session_cfg["session"]["state"]))
                os.remove(tools.config.session_defaults["config_path"])
        logging.debug("Container manager is waiting for session to load")
        while not os.path.exists(tools.config.session_defaults["config_path"]):
            time.sleep(1)
        
        # Load session configs
        session_cfg = tools.config.load_session()
        
        # Generate props
        make_prop(args.work + "/waydroid.prop")

        # Networking
        command = [tools.config.tools_src +
                   "/data/scripts/waydroid-net.sh", "start"]
        tools.helpers.run.root(args, command, check=False)

        # Sensors
        tools.helpers.run.root(
            args, ["waydroid-sensord", "/dev/" + args.HWBINDER_DRIVER], output="background")

        # Mount rootfs
        helpers.images.mount_rootfs(args, cfg["waydroid"]["images_path"])

        # Mount data
        helpers.mount.bind(args, session_cfg["session"]["waydroid_data"],
                           tools.config.defaults["data"])

        # Cgroup hacks
        if which("start"):
            command = ["start", "cgroup-lite"]
            tools.helpers.run.root(args, command, check=False)
        helpers.mount.umount_all(args, "/sys/fs/cgroup/schedtune")

        #TODO: remove NFC hacks
        if which("stop"):
            command = ["stop", "nfcd"]
            tools.helpers.run.root(args, command, check=False)

        # Set permissions
        set_permissions()
        
        helpers.lxc.start(args)
        session_cfg["session"]["state"] = helpers.lxc.status(args)
        tools.config.save_session(session_cfg)

        if not hasattr(args, 'hardwareLoop'):
            services.hardware_manager.start(args)

        signal.signal(signal.SIGINT, signal_handler)
        while os.path.exists(tools.config.session_defaults["config_path"]):
            session_cfg = tools.config.load_session()
            if session_cfg["session"]["state"] == "STOPPED":
                services.hardware_manager.stop(args)
                sys.exit(0)
            elif session_cfg["session"]["state"] == "UNFREEZE":
                session_cfg["session"]["state"] = helpers.lxc.status(args)
                tools.config.save_session(session_cfg)
                unfreeze(args)
            time.sleep(1)

        logging.warning("session manager stopped, stopping container and waiting...")
        stop(args)
        start(args)
    else:
        logging.error("WayDroid container is {}".format(status))

def stop(args):
    status = helpers.lxc.status(args)
    if status != "STOPPED":
        helpers.lxc.stop(args)
        if os.path.exists(tools.config.session_defaults["config_path"]):
            session_cfg = tools.config.load_session()
            session_cfg["session"]["state"] = helpers.lxc.status(args)
            tools.config.save_session(session_cfg)

        # Networking
        command = [tools.config.tools_src +
                   "/data/scripts/waydroid-net.sh", "stop"]
        tools.helpers.run.root(args, command, check=False)

        #TODO: remove NFC hacks
        if which("start"):
            command = ["start", "nfcd"]
            tools.helpers.run.root(args, command, check=False)

        # Sensors
        if which("waydroid-sensord"):
            command = ["pidof", "waydroid-sensord"]
            pid = tools.helpers.run.root(args, command, check=False, output_return=True)
            if pid:
                command = ["kill", "-9", pid]
                tools.helpers.run.root(args, command, check=False)

    else:
        logging.error("WayDroid container is {}".format(status))

def freeze(args):
    status = helpers.lxc.status(args)
    if status == "RUNNING":
        helpers.lxc.freeze(args)
        if os.path.exists(tools.config.session_defaults["config_path"]):
            session_cfg = tools.config.load_session()
            session_cfg["session"]["state"] = helpers.lxc.status(args)
            tools.config.save_session(session_cfg)
    else:
        logging.error("WayDroid container is {}".format(status))

def unfreeze(args):
    status = helpers.lxc.status(args)
    if status == "FROZEN":
        helpers.lxc.unfreeze(args)
        if os.path.exists(tools.config.session_defaults["config_path"]):
            session_cfg = tools.config.load_session()
            session_cfg["session"]["state"] = helpers.lxc.status(args)
            tools.config.save_session(session_cfg)
    else:
        logging.error("WayDroid container is {}".format(status))
