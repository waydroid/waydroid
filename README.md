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
image based on [LineageOS](https://lineageos.org/). The tooling supports
Android 13 through Android 16 (API 36, LineageOS 20–23): the service-manager
protocol and HAL detection follow the image's API level at runtime
(`tools/helpers/protocol.py`, `tools/helpers/lxc.py`).

The official images on the Waydroid OTA channel are still built on Android 13;
newer LineageOS 22/23 (Android 15/16) images are available as community builds
(e.g. [waydroid-builds](https://github.com/supechicken/waydroid-builds)) and
can be installed with a custom channel:

```
waydroid init -c <system channel> -v <vendor channel> -r lineage
```

Upstream tracks the official image rebuild in
[waydroid/waydroid#2229](https://github.com/waydroid/waydroid/issues/2229).

## Install

See install instructions [here](https://docs.waydro.id/usage/install-on-desktops)

## Documentation

Our documentation can be found at [docs.waydro.id](https://docs.waydro.id)

## Reporting bugs

If you have found an issue with Waydroid, please [file a bug](https://github.com/Waydroid/waydroid/issues/new/choose).

## Get in Touch

If you want to get in contact with the developers please feel free to join the
*Waydroid* groups in [Matrix](https://matrix.to/#/#waydroid:matrix.org) or [Telegram](https://t.me/WayDroid).

Our website can be found at [waydro.id](https://waydro.id/)
