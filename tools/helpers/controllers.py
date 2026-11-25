# Copyright 2026 The Waydroid Authors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for power-cycling USB gamepads through sysfs.

This is the library version of the controller_reset.py script: it detaches a
gamepad's USB interfaces from their drivers and attaches them again, which
makes the host (and therefore Waydroid) re-enumerate the controller.

All sysfs writes performed here need root.  They are meant to be called from
the root-owned container manager, so no interactive sudo/pkexec prompt is
needed when starting a Waydroid session as a regular user.

Rather than sleeping for a fixed number of seconds, we wait for the kernel to
actually finish each step: the driver symlink must disappear after unbind and
reappear after bind, and any input node that was present must be removed and
then recreated.  This adapts to each machine instead of relying on a magic
delay.
"""

import glob
import logging
import os
import subprocess
import time

SYS_USB_DEVICES = "/sys/bus/usb/devices"
SYS_USB_DRIVERS = "/sys/bus/usb/drivers"
SYS_INPUT_CLASS = "/sys/class/input"
DEV_INPUT = "/dev/input"

# Safety caps for the event-driven waits.  These are timeouts, not delays:
# we return as soon as the expected state is observed.
POLL_INTERVAL = 0.05
SETTLE_TIMEOUT = 10.0

CONTROLLER_DRIVERS = {
    "xpad", "hid-generic", "usbhid", "hid-sony", "hid-microsoft",
    "hid-nintendo", "hid-logitech", "hid-steam", "xone", "ds4drv",
    "ps3", "ps4",
}

CONTROLLER_NAME_HINTS = ("controller", "gamepad", "joystick")


def _hex(value):
    """Parse a sysfs hexadecimal byte; return None when unavailable."""
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


def _read_sysfs(path):
    try:
        with open(path, "r") as handle:
            return handle.read().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _write_sysfs(path, value):
    try:
        with open(path, "w") as handle:
            handle.write(value)
        return True, ""
    except OSError as e:
        return False, str(e)


def _interface_driver(interface):
    """Return the name of the driver currently bound to an interface."""
    driver_link = os.path.join(interface, "driver")
    if os.path.islink(driver_link):
        return os.path.basename(os.readlink(driver_link))
    return ""


def _is_input_interface(iface_class, driver, product):
    """Decide whether a USB interface is one Waydroid needs re-enumerated.

    This matches the original controller_reset.py behaviour: all HID (class
    03) interfaces are included, including keyboards and mice.  Waydroid
    needs every input device replugged, not just gamepads -- excluding
    keyboards/mice makes them invisible inside Android.  Vendor-specific
    (class ff) interfaces count when a known controller driver is bound or
    the product name says gamepad/joystick/controller.
    """
    name_hint = any(hint in (product or "").lower() for hint in CONTROLLER_NAME_HINTS)
    iface_class = _hex(iface_class)

    if iface_class == 0x03:
        return True

    if iface_class == 0xFF:
        return driver in CONTROLLER_DRIVERS or name_hint

    return name_hint and driver in CONTROLLER_DRIVERS


def _input_nodes(interface):
    """Return /dev/input/event names currently belonging to this interface.

    The input device is a *child* of the USB interface in sysfs, e.g.
    ``.../2-2:1.0/input/input41``, so a plain equality check never matches.
    Accept any input device whose sysfs path is under the interface.
    """
    nodes = set()
    target = os.path.realpath(interface)
    prefix = target + os.sep
    for event in glob.glob(os.path.join(SYS_INPUT_CLASS, "event*")):
        try:
            device = os.path.realpath(os.path.join(event, "device"))
            if device == target or device.startswith(prefix):
                nodes.add(os.path.basename(event))
        except OSError:
            continue
    return nodes


def _nodes_present(nodes):
    """Nodes that still exist in either /dev/input or sysfs."""
    return {node for node in nodes
            if os.path.exists(os.path.join(DEV_INPUT, node)) or
               os.path.exists(os.path.join(SYS_INPUT_CLASS, node))}


def _udev_settle():
    """Wait until udev has finished processing the disconnect events.

    This is a proper 'system is quiescent' signal rather than a fixed sleep.
    It is skipped silently if udevadm is not available.
    """
    try:
        subprocess.run(["udevadm", "settle", "--timeout=10"],
                       timeout=12, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _wait_until(predicate, description):
    """Poll until predicate() is true or the safety timeout expires."""
    deadline = time.monotonic() + SETTLE_TIMEOUT
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            logging.debug("Timed out waiting for {}".format(description))
            return False
        time.sleep(POLL_INTERVAL)


def find_controller_devices():
    """Find USB devices with interfaces Waydroid needs re-enumerated.

    Includes HID keyboards/mice as well as gamepads.  When a device qualifies,
    all of its interfaces are returned (as in the original script) so a
    composite device gets fully replugged.
    """
    controllers = []

    for dev_path in sorted(glob.glob(os.path.join(SYS_USB_DEVICES, "*"))):
        dev_num = os.path.basename(dev_path)
        # Interface directories are named like "1-1:1.0"; only look at devices.
        if ":" in dev_num or not dev_num or not dev_num[0].isdigit():
            continue

        vendor = _read_sysfs(os.path.join(dev_path, "idVendor"))
        product_id = _read_sysfs(os.path.join(dev_path, "idProduct"))
        product = _read_sysfs(os.path.join(dev_path, "product"))

        interfaces = []
        has_input_interface = False
        for iface in sorted(glob.glob(os.path.join(dev_path, "*:*"))):
            if not os.path.isdir(iface):
                continue
            driver = _interface_driver(iface)
            iface_class = _read_sysfs(os.path.join(iface, "bInterfaceClass"))

            if _is_input_interface(iface_class, driver, product):
                has_input_interface = True

            interfaces.append({
                "name": os.path.basename(iface),
                "path": iface,
                "driver": driver,
            })

        if not has_input_interface:
            continue

        controllers.append({
            "device": dev_num,
            "path": dev_path,
            "vid": vendor,
            "pid": product_id,
            "product": product,
            "interfaces": interfaces,
        })

    return controllers


def unbind_interfaces(controller):
    """Detach the gamepad interfaces and wait until the kernel processed it."""
    results = []
    for iface in controller["interfaces"]:
        driver = iface["driver"]
        if not driver:
            results.append((iface["name"], False, "no driver bound"))
            continue
        unbind = os.path.join(SYS_USB_DRIVERS, driver, "unbind")
        if not os.path.exists(unbind):
            results.append((iface["name"], False, "driver {} not found".format(driver)))
            continue

        nodes_before = _input_nodes(iface["path"])
        iface["had_input_node"] = bool(nodes_before)

        success, error = _write_sysfs(unbind, iface["name"])
        if success:
            _wait_until(
                lambda: (not os.path.islink(os.path.join(iface["path"], "driver")) and
                         not _nodes_present(nodes_before)),
                "unbind of {}".format(iface["name"]))
        results.append((iface["name"], success, error))
    return results


def bind_interfaces(controller):
    """Re-attach the gamepad interfaces and wait for them to come back."""
    results = []
    for iface in controller["interfaces"]:
        driver = iface["driver"]
        if not driver:
            results.append((iface["name"], False, "no driver to bind to"))
            continue
        bind = os.path.join(SYS_USB_DRIVERS, driver, "bind")
        if not os.path.exists(bind):
            results.append((iface["name"], False, "driver {} not found".format(driver)))
            continue

        success, error = _write_sysfs(bind, iface["name"])
        if success:
            def ready():
                if not os.path.islink(os.path.join(iface["path"], "driver")):
                    return False
                if iface.get("had_input_node") and not _input_nodes(iface["path"]):
                    return False
                return True
            _wait_until(ready, "bind of {}".format(iface["name"]))
        results.append((iface["name"], success, error))
    return results


def reset_device(controller):
    """Trigger a USB port reset, if the device supports it."""
    reset_file = os.path.join(controller["path"], "reset")
    if not os.path.exists(reset_file):
        return False, "reset not supported"
    return _write_sysfs(reset_file, "1")


def _log_results(action, controller, results):
    for iface, success, error in results:
        if success:
            logging.debug("Controller {}: {} interface {}".format(
                controller["device"], action, iface))
        else:
            logging.warning("Controller {}: failed to {} interface {}: {}".format(
                controller["device"], action, iface, error))


def replug(reset=False):
    """Unbind and rebind every detected gamepad.

    Returns the number of controllers processed.  Failures are logged but
    never raised: a controller problem must not break session startup.
    """
    controllers = find_controller_devices()
    if not controllers:
        logging.info("No USB controllers found to replug")
        return 0

    for controller in controllers:
        description = "{} ({}:{})".format(
            controller["product"] or controller["device"],
            controller["vid"], controller["pid"])
        logging.info("Replugging controller {}".format(description))

        _log_results("unbind", controller, unbind_interfaces(controller))
        # Let udev and the input subsystem fully process the disconnect
        # before reconnecting, instead of guessing a fixed number of seconds.
        _udev_settle()
        _log_results("bind", controller, bind_interfaces(controller))

        if reset:
            success, error = reset_device(controller)
            if not success:
                logging.warning("Controller {}: reset failed: {}".format(
                    controller["device"], error))

    return len(controllers)


def replug_from_config(args, cfg):
    """Read the replug settings from waydroid.cfg and apply them."""
    reset = cfg["waydroid"].getboolean("replug_controllers_reset", fallback=False)
    return replug(reset=reset)
