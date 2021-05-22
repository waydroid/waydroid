#!/bin/bash
cd /home/anbox

# just in case, stop Anbox 7
stop anbox-container || true

# start cgroup-lite, else container may fail to start.
start cgroup-lite
umount -l /sys/fs/cgroup/schedtune

# start sensors hal
start anbox-sensors

# start lxc-net, that sets up lxc bridge
start lxc-net
brctl addbr anbox0

# stop nfcd to not conflict with anbox
stop nfcd

# umount rootfs if it was mounted
umount -l rootfs || true

mkdir -p /home/anbox/rootfs
mkdir -p /home/anbox/data
mount anbox_arm64_system.img rootfs
mount -o remount,ro rootfs
mount anbox_arm64_vendor.img rootfs/vendor
mount -o remount,ro rootfs/vendor
mount -o bind anbox.prop rootfs/vendor/anbox.prop

if mountpoint -q -- /odm; then
    mount -o bind /odm rootfs/odm_extra
else
    if [ -d /vendor/odm ]; then
        mount -o bind /vendor/odm rootfs/odm_extra
    fi
fi

# TODO: Move this to installer script
SKU=`getprop ro.boot.product.hardware.sku`
mount -o remount,rw rootfs/vendor
cp -p /vendor/etc/permissions/android.hardware.nfc.* rootfs/vendor/etc/permissions/
cp -p /vendor/etc/permissions/android.hardware.consumerir.xml rootfs/vendor/etc/permissions/
cp -p /odm/etc/permissions/android.hardware.nfc.* rootfs/vendor/etc/permissions/
cp -p /odm/etc/permissions/android.hardware.consumerir.xml rootfs/vendor/etc/permissions/
if [ ! -z $SKU ]; then
    cp -p /odm/etc/permissions/sku_${SKU}/android.hardware.nfc.* rootfs/vendor/etc/permissions/
    cp -p /odm/etc/permissions/sku_${SKU}/android.hardware.consumerir.xml rootfs/vendor/etc/permissions/
fi
if [ -f /vendor/lib/libladder.so ] && [ ! -f rootfs/vendor/lib/libladder.so ]; then
    cd rootfs/vendor/lib
    wget https://github.com/GS290-dev/gigaset_gs290_dump/raw/full_k63v2_64_bsp-user-10-QP1A.190711.020-1597810494-release-keys/vendor/lib/libladder.so
    cd ../../..
fi
if [ -f /vendor/lib64/libladder.so ] && [ ! -f rootfs/vendor/lib64/libladder.so ]; then
    cd rootfs/vendor/lib64
    wget https://github.com/GS290-dev/gigaset_gs290_dump/raw/full_k63v2_64_bsp-user-10-QP1A.190711.020-1597810494-release-keys/vendor/lib64/libladder.so
    cd ../../..
fi
mount -o remount,ro rootfs/vendor

# Anbox binder permissions
chmod 666 /dev/anbox-*binder

# Wayland socket permissions
chmod 777 -R /run/user/32011

# Set sw_sync permissions
chmod 777 /dev/sw_sync
chmod 777 /sys/kernel/debug/sync/sw_sync

# Media nodes permissions
chmod 777 /dev/Vcodec
chmod 777 /dev/MTK_SMI
chmod 777 /dev/mdp_sync
chmod 777 /dev/mtk_cmdq
chmod 777 /dev/video32
chmod 777 /dev/video33

lxc-start -n anbox -F -- /init
