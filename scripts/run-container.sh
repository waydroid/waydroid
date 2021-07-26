#!/bin/bash

ered() {
	echo -e "\033[31m" $@
}

egreen() {
	echo -e "\033[32m" $@
}

ewhite() {
	echo -e "\033[37m" $@
}

cd /home/anbox

if [ ! -e /dev/anbox-hwbinder ] || [ ! -e /dev/ashmem ]; then
    modprobe binder_linux devices="anbox-binder,anbox-hwbinder,anbox-vndbinder"
    modprobe ashmem_linux
    mkdir -p /dev/binderfs
    mount -t binder binder /dev/binderfs
    ln -s /dev/binderfs/* /dev/
fi
if [ ! -e /dev/anbox-hwbinder ] || [ ! -e /dev/ashmem ]; then
    ered "ERROR: Binder and ashmem nodes not found!"
    exit 1
fi

# just in case, stop Anbox 7
stop anbox-container || true

# start cgroup-lite, else container may fail to start.
start cgroup-lite
umount -l /sys/fs/cgroup/schedtune

# start sensors hal
anbox-sensord

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
chmod 666 /dev/ashmem

# Wayland and pulse socket permissions
XDG_PATH=$(cat anbox.prop | grep anbox.xdg_runtime_dir | cut -f 2- -d "=")
PULSE_PATH=$(cat anbox.prop | grep anbox.pulse_runtime_path | cut -f 2- -d "=")
chmod 666 -R $PULSE_PATH
chmod 666 -R $XDG_PATH

# Set sw_sync permissions
chmod 666 /dev/sw_sync
chmod 666 /sys/kernel/debug/sync/sw_sync

# Media nodes permissions
chmod 666 /dev/Vcodec
chmod 666 /dev/MTK_SMI
chmod 666 /dev/mdp_sync
chmod 666 /dev/mtk_cmdq
chown system /dev/video*
chgrp camera /dev/video*
chmod 660 /dev/video*

# Graphics nodes permissions
chgrp graphics /dev/dri/*
chmod 666 -R /dev/dri/*
chgrp graphics /dev/graphics/*
chmod 666 -R /dev/graphics/*
chmod 666 -R /dev/fb*

lxc-start -n anbox -F -- /init
