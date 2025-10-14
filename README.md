# Waydroid

Waydroid uses a container-based approach to boot a full Android system on a
regular GNU/Linux system like Ubuntu.

## Overview

Waydroid uses Linux namespaces (user, pid, uts, net, mount, ipc) to run a
full Android system in a container and provide Android applications on
any GNU/Linux-based platform.

The Android system inside the container has direct access to any needed hardware.

The Android runtime environment ships with a minimal customized Android system
image based on [LineageOS](https://lineageos.org/). The image is currently based
on Android 13.

## Multi-Instance Support

Waydroid supports running multiple isolated Android instances simultaneously. This allows you to:
- Run separate Android environments with different configurations
- Isolate applications and data between instances
- Test multiple Android configurations side by side

### Using Multi-Instance

To use a specific instance, add the `--instance` parameter to any Waydroid command:

```bash
# Initialize a new instance named "work"
waydroid --instance work init

# start the instance container
waydroid --instance work container start

# Start the session for the "work" instance
waydroid --instance work session start

# Show the full UI for the "work" instance
waydroid --instance work show-full-ui

# Launch an app in the "work" instance
waydroid --instance work app launch com.example.app
```

Each instance maintains its own:
- Container and filesystem
- Network configuration
- Application data
- DBus services

When no `--instance` parameter is provided, Waydroid uses the default instance compatible with previous installations.

You can run up to 16 instances at the same time.

## Documentation

Our documentation site can be found at [docs.waydro.id](https://docs.waydro.id)

## Reporting bugs

If you have found an issue with Waydroid, please [file a bug](https://github.com/Waydroid/waydroid/issues/new/choose).

## Get in Touch

If you want to get in contact with the developers please feel free to join the
*Waydroid* groups in [Matrix](https://matrix.to/#/#waydroid:matrix.org) or [Telegram](https://t.me/WayDroid).
