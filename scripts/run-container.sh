#!/bin/bash
cd /home/anbox

if [ ! -e /dev/anbox-hwbinder ] || [ ! -e /dev/ashmem ]; then
    modprobe binder_linux devices="anbox-binder,anbox-hwbinder,anbox-vndbinder"
    modprobe ashmem_linux
    mkdir /dev/binderfs
    mount -t binder binder /dev/binderfs
    ln -s /dev/binderfs/* /dev/
fi
if [ ! -e /dev/anbox-hwbinder ] || [ ! -e /dev/ashmem ]; then
    echo "ERROR: Binder and ashmem nodes not found!"
    exit
fi

# just in case, stop Anbox 7
stop anbox-container || true

# start cgroup-lite, else container may fail to start.
start cgroup-lite
umount -l /sys/fs/cgroup/schedtune

# start sensors hal
start anbox-sensors

# start anbox-net, that sets up lxc bridge
/home/anbox/anbox-net.sh start

# stop nfcd to not conflict with anbox
stop nfcd

# umount rootfs if it was mounted
umount -l rootfs || true

mount anbox_*_system.img rootfs
mount -o remount,ro rootfs
mount anbox_*_vendor.img rootfs/vendor
mount -o remount,ro rootfs/vendor
mount -o bind anbox.prop rootfs/vendor/anbox.prop
if [ -d /vendor/lib/egl ]; then
    mount -o bind /vendor/lib/egl rootfs/vendor/lib/egl
fi
if [ -d /vendor/lib64/egl ]; then
    mount -o bind /vendor/lib64/egl rootfs/vendor/lib64/egl
fi

if mountpoint -q -- /odm; then
    mount -o bind /odm rootfs/odm_extra
else
    if [ -d /vendor/odm ]; then
        mount -o bind /vendor/odm rootfs/odm_extra
    fi
fi

# Anbox binder permissions
chmod 666 /dev/anbox-*binder
chmod 777 /dev/ashmem

# Wayland and pulse socket permissions
XDG_PATH=`cat anbox.prop | grep anbox.xdg_runtime_dir | cut -f 2- -d "="`
PULSE_PATH=`cat anbox.prop | grep anbox.pulse_runtime_path | cut -f 2- -d "="`
chmod 777 -R $PULSE_PATH
chmod 777 -R $XDG_PATH

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

# Graphics nodes permissions
chmod 777 -R /dev/dri/*
chmod 777 -R /dev/graphics/*
chmod 777 -R /dev/fb*

lxc-start -n anbox -F -- /init
