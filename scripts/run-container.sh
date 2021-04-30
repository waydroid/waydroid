#!/bin/bash
cd /home/anbox

# just in case, stop Anbox 7
stop anbox-container || true
# umount rootfs if it was mounted
umount -l rootfs || true
./mount.sh

# Anbox binder permissions
chmod 666 /dev/anbox-*binder

# Wayland socket permissions
chmod 777 /run/user/32011
chmod 777 /run/user/32011/wayland-1

lxc-start -n anbox -F -- /init
