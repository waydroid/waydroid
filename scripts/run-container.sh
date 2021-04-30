#!/bin/bash
cd /home/anbox

# just in case, stop Anbox 7
stop anbox-container || true

# restart cgroupfs-mount, else container may fail to start on some devices
restart cgroupfs-mount

# stop sensorfw
# NOTE: it is temporary solution, that workes only on halium devices.
stop sensorfw

# start lxc-net, that sets up lxc bridge
start lxc-net

# umount rootfs if it was mounted
umount -l rootfs || true
./mount.sh

# Anbox binder permissions
chmod 666 /dev/anbox-*binder

# Wayland socket permissions
chmod 777 /run/user/32011
chmod 777 /run/user/32011/wayland-1

lxc-start -n anbox -F -- /init
