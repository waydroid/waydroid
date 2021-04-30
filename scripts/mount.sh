#!/bin/sh
mkdir -p /home/anbox/rootfs
cd /home/anbox
mount anbox_arm64_system.img rootfs
#mount -o remount,ro rootfs
mount -o ro anbox_arm64_vendor.img rootfs/vendor
mount -o bind default.prop rootfs/vendor/default.prop
#mount -o bind rootfs/system/lib64/vndk-sp-28 rootfs/system/lib64/vndk-sp-29
