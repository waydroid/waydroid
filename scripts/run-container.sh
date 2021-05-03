#!/bin/bash
cd /home/anbox

# just in case, stop Anbox 7
stop anbox-container || true

# start cgroup-lite, else container may fail to start.
start cgroup-lite

# stop sensorfw
# NOTE: it is temporary solution, that workes only on halium devices.
stop sensorfw

# start lxc-net, that sets up lxc bridge
start lxc-net

# umount rootfs if it was mounted
umount -l rootfs || true

mkdir -p /home/anbox/rootfs
mkdir -p /home/anbox/data
mount anbox_arm64_system.img rootfs
mount -o remount,ro rootfs
mount anbox_arm64_vendor.img rootfs/vendor
mount -o remount,ro rootfs
mount -o bind anbox.prop rootfs/vendor/anbox.prop

# Anbox binder permissions
chmod 666 /dev/anbox-*binder

# Wayland socket permissions
chmod 777 -R /run/user/32011

# Set sw_sync permissions
chmod 777 /dev/sw_sync
chmod 777 /sys/kernel/debug/sync/sw_sync

lxc-start -n anbox -F -- /init
