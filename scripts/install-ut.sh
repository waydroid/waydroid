#!/bin/bash

sudo bash << EOF
mount -o remount,rw /

mkdir /home/anbox
cd /home/anbox

# remove LD_LIBRARY_PATH from /etc/environment to make life easier
if ! grep -q "#LD_LIBRARY_PATH" /etc/environment; then
    sed -i -e "s/^LD_LIBRARY_PATH/#LD_LIBRARY_PATH/" /etc/environment
fi

echo "Installing packages"
apt update
apt install -y lxc1 || apt install -y lxc
apt install -y libgbinder sensorfw-qt5 libsensorfw-qt5-plugins || touch NO_SENSORS
if [ ! -f NO_SENSORS ]; then
    rm anbox-sensors_0.1.0_${ARCH}.deb
    wget https://github.com/Anbox-halium/anbox-sensors/releases/download/v0.1.0/anbox-sensors_0.1.0_${ARCH}.deb
    dpkg -i anbox-sensors_0.1.0_${ARCH}.deb || touch NO_SENSORS
fi

echo "Geting anbox images"
if [ -f anbox_${ARCH}_system.img ]; then
    mv anbox_${ARCH}_system.img anbox_${ARCH}_system.img.bak
    mv anbox_${ARCH}_vendor.img anbox_${ARCH}_vendor.img.bak
fi
rm -f latest-raw-images.zip
wget https://build.lolinet.com/file/lineage/anbox_${ARCH}/latest-raw-images.zip
unzip latest-raw-images.zip
mkdir -p /home/anbox/rootfs
mkdir -p /home/anbox/data

echo "Geting latest runner script"
rm -f run-container.sh
wget "$GIT_REPO/scripts/run-container.sh"
chmod +x run-container.sh
rm -f stop-container.sh
wget "$GIT_REPO/scripts/stop-container.sh"
chmod +x stop-container.sh
rm -f anbox-net.sh
wget "$GIT_REPO/scripts/anbox-net.sh"
chmod +x anbox-net.sh

if [ -f anbox.prop ]; then
    mv anbox.prop anbox.prop.bak
fi
if grep -q "anbox.display_height" anbox.prop.bak; then
    grep "anbox.display_height" anbox.prop.bak >> anbox.prop
fi
if grep -q "anbox.display_width" anbox.prop.bak; then
    grep "anbox.display_width" anbox.prop.bak >> anbox.prop
fi
if grep -q "anbox.display_height_padding" anbox.prop.bak; then
    grep "anbox.display_height_padding" anbox.prop.bak >> anbox.prop
fi
if grep -q "anbox.display_width_padding" anbox.prop.bak; then
    grep "anbox.display_width_padding" anbox.prop.bak >> anbox.prop
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
if [ -f NO_SENSORS ]; then
	echo "anbox.stub_sensors_hal=1" >> anbox.prop
	rm NO_SENSORS
fi
# TODO: Drop this
echo "anbox.active_apps=full" >> anbox.prop

# TODO: Get rid of this
rm -f vendor-fixup.sh
wget "$GIT_REPO/scripts/vendor-fixup.sh"
chmod +x vendor-fixup.sh
./vendor-fixup.sh $ARCH

echo "Geting latest lxc config"
mkdir /var/lib/lxc/anbox
cd /var/lib/lxc/anbox
rm -f config*
if [ `lxc-info --version | cut -d "." -f 1` -gt 2 ]; then
    wget "$GIT_REPO/lxc-configs/config_2"
else
    wget "$GIT_REPO/lxc-configs/config_1"
fi
mv config_* config
sed -i "s/LXCARCH/$UNAME_ARCH/" config
wget "$GIT_REPO/lxc-configs/config_nodes"
if [ ! -e /dev/hwbinder ]; then
        sed -i "/host_hwbinder/d" config_nodes
fi

if ! grep -q "module-native-protocol-unix auth-anonymous=1" /etc/pulse/touch-android9.pa; then
    echo "Pulseaudio config patching"
    sed -i "s/module-native-protocol-unix/module-native-protocol-unix auth-anonymous=1/" /etc/pulse/touch-android9.pa
fi

if [ ! -f /etc/gbinder.d/anbox.conf ]; then
    echo "Adding gbinder config"
    mkdir /etc/gbinder.d
    cd /etc/gbinder.d
    wget "$GIT_REPO/gbinder/anbox.conf"
fi

mount -o remount,ro /
EOF

echo "Going back to phablet user"

cd /home/phablet

echo "Restarting Pulseaudio service"
initctl --user stop pulseaudio
initctl --user start pulseaudio