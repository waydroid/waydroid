#!/bin/bash

echo "Generating device properties"
GRALLOC=`getprop ro.hardware.gralloc`
if [ -z $GRALLOC ] || [ ! -f /vendor/lib/hw/gralloc.$GRALLOC.so ]; then
    GRALLOC=`getprop ro.hardware`
    if [ -z $GRALLOC ] || [ ! -f /vendor/lib/hw/gralloc.$GRALLOC.so ]; then
        GRALLOC=`getprop ro.product.board`
        if [ -z $GRALLOC ] || [ ! -f /vendor/lib/hw/gralloc.$GRALLOC.so ]; then
            GRALLOC=`getprop ro.board.platform`
            if [ -z $GRALLOC ] || [ ! -f /vendor/lib/hw/gralloc.$GRALLOC.so ]; then
                GRALLOC=`getprop ro.arch`
                if [ -z $GRALLOC ] || [ ! -f /vendor/lib/hw/gralloc.$GRALLOC.so ]; then
                    GRALLOC="gbm"
                fi
            fi
        fi
    fi
fi
EGL=`getprop ro.hardware.egl`
if [ ! -z $EGL ]; then
    EGL_PROP="ro.hardware.egl=${EGL}"
fi

MEDIA_PROFILES=`getprop media.settings.xml`
if [ ! -z $MEDIA_PROFILES ]; then
    MEDIA_PROFILES_EXTRA=`getprop media.settings.xml | sed "s/vendor/vendor_extra/" | sed "s/odm/odm_extra/"`
    MEDIA_PROFILES_PROP="media.settings.xml=${MEDIA_PROFILES_EXTRA}"
fi
CCODEC=`getprop debug.stagefright.ccodec`
if [ ! -z $CCODEC ]; then
    CCODEC_PROP="debug.stagefright.ccodec=${CCODEC}"
fi

echo "Asking for root access"
sudo -s <<EOF
mount -o remount,rw /

mkdir /home/anbox
cd /home/anbox

# remove LD_LIBRARY_PATH from /etc/environment to make life easier
if ! grep -q "#LD_LIBRARY_PATH" /etc/environment; then
    sed -i -e "s/^LD_LIBRARY_PATH/#LD_LIBRARY_PATH/" /etc/environment
fi

echo "Installing packages"
apt update
apt install -y qtwayland5 qml-module-qtwayland-compositor
rm anbox-sensors_0.1.0_arm64.deb
wget https://github.com/Anbox-halium/anbox-sensors/releases/download/v0.1.0/anbox-sensors_0.1.0_arm64.deb
dpkg -i anbox-sensors_0.1.0_arm64.deb

echo "Geting anbox images"
if [ -f anbox_arm64_system.img ]; then
    mv anbox_arm64_system.img anbox_arm64_system.img.bak
    mv anbox_arm64_vendor.img anbox_arm64_vendor.img.bak
fi
rm -f latest-raw-images.zip
wget https://build.lolinet.com/file/lineage/anbox_arm64/latest-raw-images.zip
unzip latest-raw-images.zip

echo "Geting latest runner script"
rm -f run-container.sh
wget https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/run-container.sh
chmod +x run-container.sh

if [ -f anbox.prop ]; then
    mv anbox.prop anbox.prop.bak
fi
if grep -q "spurv.display_height" anbox.prop.bak; then
    grep "spurv.display_height" anbox.prop.bak >> anbox.prop
else
    echo "NOTE: Edit /home/anbox/anbox.prop based on your device screen resolution"
    echo "spurv.display_height=1920" >> anbox.prop
fi
if grep -q "spurv.display_width" anbox.prop.bak; then
    grep "spurv.display_width" anbox.prop.bak >> anbox.prop
else
    echo "NOTE: Edit /home/anbox/anbox.prop based on your device screen resolution"
    echo "spurv.display_width=1080" >> anbox.prop
fi
echo "ro.hardware.gralloc=${GRALLOC}" >> anbox.prop
echo "${EGL_PROP}" >> anbox.prop
echo "${MEDIA_PROFILES_PROP}" >> anbox.prop
echo "${CCODEC_PROP}" >> anbox.prop

echo "Geting latest lxc config"
mkdir /var/lib/lxc/anbox
cd /var/lib/lxc/anbox
rm -f config
wget https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/lxc-configs/config

if ! grep -q "module-native-protocol-unix auth-anonymous=1" /etc/pulse/touch-android9.pa; then
    echo "Pulseaudio config patching"
    sed -i "s/module-native-protocol-unix/module-native-protocol-unix auth-anonymous=1/" /etc/pulse/touch-android9.pa
fi

if [ ! -f /etc/gbinder.d/anbox.conf ]; then
    echo "Adding gbinder config"
    mkdir /etc/gbinder.d
    cd /etc/gbinder.d
    wget https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/gbinder/anbox.conf
fi

mount -o remount,ro /

echo "Going back to phablet user"
EOF
cd /home/phablet

echo "Installing anbox launcher"
rm anbox.rudiimmer_1.0_all.click
wget https://build.lolinet.com/file/lineage/anbox_arm64/anbox.rudiimmer_1.0_all.click
pkcon install-local anbox.rudiimmer_1.0_all.click --allow-untrusted

echo "Restarting Pulseaudio service"
initctl --user stop pulseaudio
initctl --user start pulseaudio

echo "Installing Finished!"
echo "Run anbox container with /home/anbox/run-container.sh on terminal"
