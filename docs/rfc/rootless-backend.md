# RFC: A rootless podman backend for Waydroid

- **Status:** Draft, for discussion.
- **Prototype:** <https://github.com/dingdang66686/waydroid-rootless>
- **Discussion:** <https://github.com/waydroid/waydroid/discussions/2455>
- **Image builder:** <https://github.com/dingdang66686/waydroid-rootless-image>
- **Scope:** a selectable backend for `waydroid/waydroid`; this document is
  not a patch series.

## 1. Summary

Waydroid currently boots Android in a rootful LXC container.  This RFC proposes
a second backend that boots the same Android image in a **rootless podman**
container.

The runtime contract stays small:

- one OCI image (`podman_image`);
- one named podman volume mounted at `/data`;
- the user's Wayland, Pulse and DRI sockets.

The existing Waydroid CLI, D-Bus API, session manager and container interface
remain in place.  The backend is selected through `container_backend`; the LXC
backend remains available.

A working prototype exists in the fork above.  It boots Android 13 to
`sys.boot_completed=1` and has been exercised with networking, ADB, input,
audio, rendering, app install/remove and a local ARM translation overlay.

## 2. Motivation

- No root daemon and no root-owned LXC state.
- Per-user state and a per-user systemd service.
- One immutable image plus a named `/data` volume, which makes image updates
  and local overlays easier to reason about.
- A backend boundary that can be tested independently of the existing LXC
  runtime.

Non-goals for this RFC:

- replacing LXC for existing users;
- changing the Android image format;
- solving every rootless kernel/cgroup limitation in the first iteration;
- distributing proprietary native-bridge binaries.

## 3. Architecture

```
Waydroid CLI / D-Bus session
        |
        v
 podman backend (user)  --->  pasta network / ADB loopback
        |
        v
 rootless podman + crun
        |
        v
 Android 13 rootfs (OCI image) + named /data volume
```

The host provides only the user session, the OCI image store, the podman
runtime and the graphics/audio sockets.  Android continues to own its own init,
zygote, services and HALs inside the container.

### 3.1 User namespace and storage

The backend runs entirely in the calling user's account.  The tested mapping is:

```text
container 0       -> host 1000
container 1..     -> host 100000..231070
container INT_MAX -> host 231071
```

`/etc/subuid` and `/etc/subgid` therefore need a **131072**-UID range.  This is
larger than a typical desktop range because Android creates a large number of
per-app and per-service UIDs; netd installs routing rules across that range.

Rootless podman uses the user's native overlay storage when the kernel supports
it.  Native overlay requires kernel >= 5.13; the test host uses kernel 7.2.

### 3.2 Networking

The container uses pasta.  Waydroid passes `--config-net` to the network helper;
rootless pasta DHCP should be used instead, so the backend filters that option
before invoking pasta.  The result is a normal DHCP-configured interface
inside Android, with IPv4 and IPv6 working.

ADB uses a normal podman loopback publish:

```text
-p 127.0.0.1:<podman_adb_port>:5555
```

`waydroid adb connect` targets that address.  No host-side ADB daemon or
network namespace trick is required.

### 3.3 Binder

Binderfs is created **inside** the container.  Rootless podman cannot claim the
host binder context manager, so the backend provides a small fd broker:

1. The container starts `wd-broker` with access to its binderfs nodes.
2. The broker exposes a host-owned Unix socket.
3. The host-side Waydroid process passes binder fds over `SCM_RIGHTS`.
4. gbinder on the host uses those fds for session services.

This keeps Android's binder services reachable without a host binderfs or
root privileges.

### 3.4 Data volume and sockets

`/data` is a named podman volume.  Android's own `init.rc` sets its ownership
and mode:

```text
chown system system /data
chmod 0771 /data
```

So the normal runtime value is **1000:1000 (system:system)**, not root.  The
volume root is left to Android init; no host-side chown is needed.  The host
mountpoint stores the container's mapped ownership.

`/dev/socket` is also **container-local**.  This image does not pre-create the
directory, and Android's property service fails with ENOENT if it is missing.
The backend starts init at its second stage (the first stage needs root-only
`mknod`/proc operations), so the normal first-stage creation of this directory
is skipped.  A small tmpfs is mounted at `/dev/socket` instead; Android creates
the sockets there and they disappear with the container.  The host never uses
these sockets, so a host bind is neither needed nor desirable: it only leaks
stale sockets and host permissions into Android.

### 3.5 Image updates and local overlays

The runtime only needs `podman_image`.  The image builder lives outside the
Waydroid tree (see the link at the top) and publishes a plain patched Android
rootfs.

A user may keep a local file-tree overlay at `$WORK/overlay`:

```text
overlay/
  system/...
  vendor/...
```

At container start the application applies the overlay as a **COPY layer** on
top of the configured image:

```text
podman build  FROM <podman_image>  COPY <overlay> /
```

containers/storage shares the base layers; only the overlay layer is added.
The layer is rebuilt when the overlay content or base image ID changes.  This
keeps private compatibility layers local and avoids any runtime overlay or
host mutation of the Android tree.  Deletions and property merging are not part
of this basic file-tree mechanism.

### 3.6 Startup sequence

1. The per-user `waydroid.service` starts `waydroid session start`.
2. The backend prepares the named data volume.
3. The local overlay is checked and, if needed, rebuilt as a layer.
4. The container starts with the rootfs image, `/data`, a local
   `/dev/socket` tmpfs, Wayland/Pulse/DRI and the binder broker.
5. The host sets the Android binder protocol from the image's build.prop.

`container restart` repeats the overlay check.  There is no file watcher;
overlay changes take effect on the next start.

## 4. Feasibility evidence

The prototype has been tested on Arch Linux on x86_64 with podman 6.1 and
kernel 7.2.  The following were observed:

| Area | Result |
| --- | --- |
| Boot | `sys.boot_completed=1` |
| Display | SurfaceFlinger starts; Android UI renders |
| Network | DHCP IPv4/IPv6; DNS works |
| ADB | host loopback publish reaches Android adbd |
| Input | keyboard/mouse via the host compositor |
| Audio | Pulse path works |
| Apps | install, list and remove work |
| Properties | `prop get/set` through the Android IPlatform service |
| Freeze | podman pause/unpause; Android resumes |
| Local overlay | file-tree COPY layer applies and boots |
| ARM bridge | local overlay supplies the native bridge and binfmt handlers |

These are prototype measurements, not a claim that every Android feature or
every host kernel is supported.

## 5. Remaining hard points

### 5.1 UID range

The 131072-UID submap is required.  The backend should fail early with a clear
error if the range is missing, rather than letting Android fail later during
netd setup.

### 5.2 Pasta `--config-net`

Waydroid's network helper passes an LXC-oriented flag.  The rootless backend
filters it and uses pasta DHCP.  Upstream should provide a backend capability
for this rather than each backend parsing the shared command line.

### 5.3 Image-side init overrides

Three Android init changes are currently made in the image build:

- `bpfloader.rc`: publish `bpf.progs_loaded=1` instead of loading eBPF;
- zygote: drop `priority -20`, which needs `CAP_SYS_NICE` in the initial
  namespace;
- LineageOS keychord watcher: drop `keycodes`, which blocks on a host input
  FIFO.

These belong in the Android image/product tree, not in the runtime.

### 5.4 Cgroup, mknod, BPF and iptables

Rootless containers cannot provide every rootful capability.  The prototype
works around the common cases with cgroup unmasking, device nodes and a
userspace network path.  Features that depend on host firewall rules or eBPF
may remain unsupported; they should be documented rather than silently
half-work.

## 6. Security and limitations

- The backend is rootless; a container escape is bounded by the user namespace.
- The image is immutable; `/data` is the persistent state.
- The LXC backend remains for users who need rootful features.
- Sensors are currently a stub on the test host.
- The prototype is not an upstream-ready patch series.  It is a feasibility
  implementation and needs review, tests and cleanup before merge.
- The image builder and local overlays are separate from this repository.

## 7. Upstreaming plan

1. Define a small backend capability interface (network mode, binder, image
   requirements) instead of backend-specific argument rewriting.
2. Land the podman backend behind `container_backend=podman`; keep LXC as the
   default until the test matrix is broad enough.
3. Add a per-user systemd unit and keep rootful services untouched for LXC.
4. Move the three init overrides into the Android image/product build.
5. Add CI for the CLI/session tests and a documented manual boot test for the
   actual Android container.
6. Document AOSP `/data` ownership and the container-local `/dev/socket`.

## 8. Open questions

- Should rootless podman be an official image variant or only a backend?
- How should the project publish/recommend images without taking ownership of
  proprietary native-bridge layers?
- Which rootless kernel/cgroup features are acceptable to require, and which
  should remain best-effort?
- How should local overlays be represented in upstream documentation?

## 9. References

- Prototype fork:
  <https://github.com/dingdang66686/waydroid-rootless>
- Discussion:
  <https://github.com/waydroid/waydroid/discussions/2455>
- Image builder:
  <https://github.com/dingdang66686/waydroid-rootless-image>
- Architecture diagram:
  <https://raw.githubusercontent.com/dingdang66686/waydroid-rootless/main/docs/rootless-architecture.png>

This RFC was prepared with assistance from **DeepSeek Flash V4.1**.
