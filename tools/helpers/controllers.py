# Copyright 2026 The Waydroid Authors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for power-cycling USB gamepads through sysfs.

It detaches a gamepad's USB interfaces from their drivers and attaches them
again, which makes the host (and therefore Waydroid) re-enumerate the
controller.  Mice, keyboards, touchpads and touchscreens are deliberately left
alone: cycling those while a Waydroid session is running can leave Android's
input stack with a half-pressed pointer, so taps animate but never click.
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
    "xpad", "hid-sony", "hid-microsoft", "hid-nintendo", "hid-logitech",
    "hid-steam", "xone", "ds4drv", "ps3", "ps4",
}

CONTROLLER_NAME_HINTS = ("controller", "gamepad", "joystick")

# evdev capability bits (see linux/input-event-codes.h).  These are used to
# tell a gamepad/joystick apart from a mouse, keyboard or touchscreen before
# deciding that an interface may be replugged.
MOUSE_BUTTONS = set(range(0x110, 0x118))       # BTN_LEFT .. BTN_TASK
TABLET_BUTTONS = set(range(0x140, 0x160))      # BTN_TOOL_*/BTN_TOUCH/BTN_STYLUS
GAMEPAD_BUTTONS = (set(range(0x120, 0x140)) |  # BTN_JOYSTICK / BTN_GAMEPAD
                   set(range(0x220, 0x230)) |  # BTN_DPAD_*
                   set(range(0x2c0, 0x2d0)))   # BTN_TRIGGER_HAPPY*
POINTER_REL = {0x00, 0x01}                     # REL_X, REL_Y
GAMEPAD_ABS = set(range(0x00, 0x0b)) | set(range(0x10, 0x18))
TOUCH_ABS = set(range(0x2f, 0x40))             # ABS_MT_*


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


def _capability_bits(path):
    """Parse a sysfs evdev capability mask (space separated 32-bit hex words)."""
    bits = set()
    for index, word in enumerate(_read_sysfs(path).split()):
        try:
            value = int(word, 16)
        except ValueError:
            continue
        for bit in range(32):
            if value & (1 << bit):
                bits.add(index * 32 + bit)
    return bits


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


def _input_capabilities(node):
    """Return the (abs, rel, key) capability bit sets of an event node."""
    device = os.path.realpath(os.path.join(SYS_INPUT_CLASS, node, "device"))
    return tuple(
        _capability_bits(os.path.join(device, "capabilities", kind))
        for kind in ("abs", "rel", "key"))


def _looks_like_gamepad(node):
    """True when an event node belongs to a joystick/gamepad, not a pointer."""
    abs_bits, rel_bits, key_bits = _input_capabilities(node)
    if abs_bits & TOUCH_ABS or key_bits & (MOUSE_BUTTONS | TABLET_BUTTONS):
        return False
    if key_bits & GAMEPAD_BUTTONS:
        return True
    return bool(abs_bits & GAMEPAD_ABS) and not (rel_bits & POINTER_REL)


def _is_pointing_device(node):
    """True for mice, touchpads, touchscreens and graphics tablets."""
    abs_bits, rel_bits, key_bits = _input_capabilities(node)
    if key_bits & GAMEPAD_BUTTONS:
        return False
    return bool((abs_bits & TOUCH_ABS) or
                (key_bits & (MOUSE_BUTTONS | TABLET_BUTTONS)) or
                (rel_bits & POINTER_REL))


def _is_gamepad_interface(interface, product):
    """Decide whether a USB interface may be safely replugged.

    A composite USB device can contain a gamepad plus other input devices.
    Only interfaces that actually expose joystick/gamepad capabilities (or
    that belong to a known controller driver without an evdev node) qualify.
    This keeps the mouse used for clicking Android's UI out of the replug.
    """
    nodes = _input_nodes(interface)
    if nodes:
        if any(_is_pointing_device(node) for node in nodes):
            return False
        if any(_looks_like_gamepad(node) for node in nodes):
            return True

    # Fallback for vendor-specific controller interfaces that don't expose an
    # evdev node (extra xpad interfaces, for example).
    driver = _interface_driver(interface)
    iface_class = _hex(_read_sysfs(os.path.join(interface, "bInterfaceClass")))
    name_hint = any(hint in (product or "").lower()
                    for hint in CONTROLLER_NAME_HINTS)
    return ((iface_class == 0xFF and driver in CONTROLLER_DRIVERS) or
            (name_hint and driver in CONTROLLER_DRIVERS))


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
    """Find USB devices with gamepad/joystick interfaces to re-enumerate.

    Keyboards, mice, touchpads and touchscreens are intentionally excluded:
    rebinding them while Waydroid is running can leave clicks half-pressed,
    where the button animates but never activates.
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
        for iface in sorted(glob.glob(os.path.join(dev_path, "*:*"))):
            if not os.path.isdir(iface) or not _is_gamepad_interface(iface, product):
                continue
            interfaces.append({
                "name": os.path.basename(iface),
                "path": iface,
                "driver": _interface_driver(iface),
            })

        if not interfaces:
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


def _log_results(action, controller, results):
    for iface, success, error in results:
        if success:
            logging.debug("Controller {}: {} interface {}".format(
                controller["device"], action, iface))
        else:
            logging.warning("Controller {}: failed to {} interface {}: {}".format(
                controller["device"], action, iface, error))


def replug():
    """Unbind and rebind every detected gamepad/joystick.

    Returns the number of devices processed.  Failures are logged but
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

    return len(controllers)
