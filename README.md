<img align="left" src="data/AppIcon.png" width="64">

# Waydroid

Waydroid uses a container-based approach to boot a full Android system on a
regular GNU/Linux system.

## Overview

Waydroid uses Linux namespaces (user, pid, uts, net, mount, ipc) to run a
full Android system in a container and provide Android applications on
any GNU/Linux-based platform.

The Android system inside the container has direct access to any needed hardware.

The Android runtime environment ships with a minimal customized Android system
image based on [LineageOS](https://lineageos.org/). The image is currently based
on Android 13.

## Install

See install instructions [here](https://docs.waydro.id/usage/install-on-desktops)

## Documentation

Our documentation can be found at [docs.waydro.id](https://docs.waydro.id)

## Replugging USB controllers on session start

Some USB gamepads are only picked up correctly by Android if they are
disconnected and reconnected after Waydroid has started. Set the following in
`/var/lib/waydroid/waydroid.cfg` to do this automatically whenever a Waydroid
session starts:

```ini
[waydroid]
replug_controllers_on_startup = True
# Optional setting:
# replug_controllers_reset = False
```

Every detected USB input device is replugged: gamepads, joysticks, keyboards
and mice (all USB HID class 03 interfaces, plus vendor-specific devices with
known controller drivers). There are no VID/PID filters. Waydroid needs all
input devices re-enumerated, not just gamepads.

Timing is event-driven, not a fixed sleep. The replug is triggered as soon as
Android's platform binder service appears during system-server startup, so the
controller starts enumerating while Android's input stack is coming up instead
of after the UI is already usable. A user-unlock fallback covers builds where
that service appears too early. For each device, Waydroid then waits
until the driver symlink is gone, the input device node has disappeared from
both `/dev/input` and sysfs, and udev has finished processing the disconnect
(`udevadm settle`). Only then is the driver bound again, and it waits for the
input node to return. This adapts to each machine instead of relying on a
hardcoded delay.

`replug_controllers_reset` (default: `False`) additionally writes `1` to the
device's sysfs `reset` file after the driver has been rebound. That triggers a
full USB port reset, i.e. a real hardware-level re-enumeration, rather than
just detaching and reattaching the kernel driver. It can help controllers that
still aren't detected after a plain driver cycle, but it is more disruptive:
it briefly drops the device, may affect other devices on the same hub, and is
silently skipped with a log message if the device doesn't support it. Leave it
off unless you need it.

The sysfs `bind`/`unbind` operations are performed by the already privileged
`waydroid-container` service, so no `sudo`, `pkexec`, or password prompt is
needed to start a session as a regular user.

## Reporting bugs

If you have found an issue with Waydroid, please [file a bug](https://github.com/Waydroid/waydroid/issues/new/choose).

## Get in Touch

If you want to get in contact with the developers please feel free to join the
*Waydroid* groups in [Matrix](https://matrix.to/#/#waydroid:matrix.org) or [Telegram](https://t.me/WayDroid).

Our website can be found at [waydro.id](https://waydro.id/)
