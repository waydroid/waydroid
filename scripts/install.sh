#!/bin/bash

echo "Generating device properties"
rm -f generate-props.sh
wget https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/generate-props.sh
chmod +x generate-props.sh
. generate-props.sh

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
rm -f stop-container.sh
wget https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/stop-container.sh
chmod +x stop-container.sh

if [ -f anbox.prop ]; then
    mv anbox.prop anbox.prop.bak
fi
if grep -q "anbox.display_height" anbox.prop.bak; then
    grep "anbox.display_height" anbox.prop.bak >> anbox.prop
else
    echo "NOTE: Edit /home/anbox/anbox.prop based on your device screen resolution"
    echo "anbox.display_height=1920" >> anbox.prop
fi
if grep -q "anbox.display_width" anbox.prop.bak; then
    grep "anbox.display_width" anbox.prop.bak >> anbox.prop
else
    echo "NOTE: Edit /home/anbox/anbox.prop based on your device screen resolution"
    echo "anbox.display_width=1080" >> anbox.prop
fi
echo "${GRALLOC_PROP}" >> anbox.prop
echo "${EGL_PROP}" >> anbox.prop
echo "${MEDIA_PROFILES_PROP}" >> anbox.prop
echo "${CCODEC_PROP}" >> anbox.prop
echo "${EXT_LIB_PROP}" >> anbox.prop
echo "${VULKAN_PROP}" >> anbox.prop
echo "${DPI_PROP}" >> anbox.prop
echo "${GLES_VER_PROP}" >> anbox.prop
echo "${XDG_PROP}" >> anbox.prop
echo "${WAYLAND_DISP_PROP}" >> anbox.prop
echo "${PULSE_PROP}" >> anbox.prop

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
echo "Run anbox container with \"sudo /home/anbox/run-container.sh\" on terminal"
echo "Stop anbox container with \"sudo /home/anbox/stop-container.sh\" on terminal"
