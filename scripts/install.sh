#!/bin/bash

# run as root/with sudo

# disable MTP/ADB to have USB network
echo "manual" > /etc/init/mtp-state.override

# remove LD_LIBRARY_PATH from /etc/environment to make life easier
sed -i -e "s/^LD_LIBRARY_PATH/#LD_LIBRARY_PATH/" /etc/environment

mount -o remount,rw /
apt update
apt install -y qtwayland5 qml-module-qtwayland-compositor
mount -o remount,ro /

chown -R phablet:phablet /home/phablet/pure-qml

cd /home/anbox
tar xfpz data.tar.gz --numeric-owner
mkdir -p rootfs
