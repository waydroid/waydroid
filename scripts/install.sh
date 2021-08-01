#!/bin/bash
# Authors:          https://github.com/Anbox-halium/anbox-halium
# Modified by:      https://github.com/sickcodes

USER_ANBOX_PASSWORD=anbox
SUPPORTED_ARCHS=(x86_64 aarch64 armv8l)
GENERATE_PROPS_URL='https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/generate-props.sh'


UNAME_ARCH="$(uname -m)"

for ARCH in "${SUPPORTED_ARCHS[@]}"; do
    if [ "${UNAME_ARCH}" = "${ARCH}" ]; then
        export ARCH
        break
    fi
done

echo "Architecture: ${ARCH}"

ANBOX_SENSORS_URL="https://github.com/Anbox-halium/anbox-sensors/releases/download/v0.1.0/anbox-sensors_0.1.0_${ARCH}.deb"

if [ -z "${ARCH}" ]; then
    echo "ERROR: Your system with arch ${UNAME_ARCH} is not supported"
    exit 1
fi

case "${UNAME_ARCH}" in
    aarch64 )   export ARCH="arm64"
        ;;
    armv8l )    export ARCH="arm64"
        ;;
    armv7l )    export ARCH="arm"
        ;;
    i386 )      export ARCH="x86"
        ;;
    i686 )      export ARCH="x86"
        ;;
esac

# replaceable by git pull?
echo "Generating device properties"

command wget || { echo "Install wget: apt install wget -y" && exit 1 ; }
command getprop || { echo "See system requirements: https://github.com/Anbox-halium/anbox-halium" && exit 1 ; }

wget -O generate-props.sh "${GENERATE_PROPS_URL}"
source generate-props.sh

echo "Asking for root access..."

# quit if anything happens while doing sudo stuff...
set -e

sudo /bin/bash <<EOF
# mount as rewritable...
mount -o remount,rw /

# add a user named anbox
getent passwd anbox &> /dev/null || useradd anbox -p "${USER_ANBOX_PASSWORD}"

mkdir -p /home/anbox

cd /home/anbox

chown -R anbox /home/anbox

# # remove LD_LIBRARY_PATH from /etc/environment to make life easier
# if ! grep -q "#LD_LIBRARY_PATH" /etc/environment; then
#     sed -i -e "s/^LD_LIBRARY_PATH/#LD_LIBRARY_PATH/" /etc/environment
# fi
unset LD_LIBRARY_PATH

echo "Installing packages..."
apt update -y
apt install -y lxc1 || apt install -y lxc


if ! [ "\$(apt install -y libgbinder sensorfw-qt5 libsensorfw-qt5-plugins)" ]; then
    rm "anbox-sensors_0.1.0_${ARCH}.deb"
    dpkg -i "anbox-sensors_0.1.0_${ARCH}.deb" || touch NO_SENSORS
fi

dpkg -l libgbinder sensorfw-qt5 libsensorfw-qt5-plugins || exit 1

echo "Geting anbox images..."
if [ -f "anbox_${ARCH}_system.img" ]; then
    mv "anbox_${ARCH}_system.img" "anbox_${ARCH}_system.img.bak"
    mv "anbox_${ARCH}_vendor.img" "anbox_${ARCH}_vendor.img.bak"
fi

wget -O latest-raw-images.zip "https://build.lolinet.com/file/lineage/anbox_${ARCH}/latest-raw-images.zip"
unzip latest-raw-images.zip
mkdir -p /home/anbox/rootfs
mkdir -p /home/anbox/data

echo "Geting latest runner script..."
wget -O run-container.sh https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/run-container.sh
wget -O stop-container.sh https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/stop-container.sh
wget -O anbox-net.sh https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/anbox-net.sh

chmod +x anbox-net.sh stop-container.sh run-container.sh


REUSABLE_SETTINGS=(
anbox.display_height
anbox.display_height_padding
anbox.display_width_padding
)

if [ -e anbox.prop ]; then
    mv anbox.prop anbox.prop.bak

    # re-use old resolutions
    for SETTING in "\${REUSABLE_SETTINGS[@]}"; do
        grep -qs "\${SETTING}" anbox.prop.bak >> anbox.prop || true
    done

fi

tee -a anbox.prop <<EOFEOF
${GRALLOC_PROP}
${EGL_PROP}
${MEDIA_PROFILES_PROP}
${CCODEC_PROP}
${EXT_LIB_PROP}
${VULKAN_PROP}
${DPI_PROP}
${GLES_VER_PROP}
${XDG_PROP}
${WAYLAND_DISP_PROP}
${PULSE_PROP}
EOFEOF

if ! [ -e NO_SENSORS ]; then
	echo "anbox.stub_sensors_hal=1" >> anbox.prop
fi

# TODO: Drop this
echo "anbox.active_apps=full" >> anbox.prop

# TODO: Get rid of this
# https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/vendor-fixup.sh

mkdir -p /home/anbox/tmp_vendor
mount "/home/anbox/anbox_${ARCH}_vendor.img" /home/anbox/tmp_vendor

export SKU="\$(getprop ro.boot.product.hardware.sku 2>/dev/null)"

cp -p /vendor/etc/permissions/android.hardware.nfc.*            /home/anbox/tmp_vendor/etc/permissions/
cp -p /vendor/etc/permissions/android.hardware.consumerir.xml   /home/anbox/tmp_vendor/etc/permissions/
cp -p /odm/etc/permissions/android.hardware.nfc.*               /home/anbox/tmp_vendor/etc/permissions/
cp -p /odm/etc/permissions/android.hardware.consumerir.xml      /home/anbox/tmp_vendor/etc/permissions/

if [ "${SKU}" ]; then
    cp -p "/odm/etc/permissions/sku_${SKU}"/android.hardware.nfc.*          /home/anbox/tmp_vendor/etc/permissions/
    cp -p "/odm/etc/permissions/sku_${SKU}"/android.hardware.consumerir.xml /home/anbox/tmp_vendor/etc/permissions/
fi

if [ -f /vendor/lib/libladder.so ] && ! [ -f /home/anbox/tmp_vendor/lib/libladder.so ]; then

    wget -O /home/anbox/tmp_vendor/lib/libladder.so \
        https://github.com/GS290-dev/gigaset_gs290_dump/raw/full_k63v2_64_bsp-user-10-QP1A.190711.020-1597810494-release-keys/vendor/lib/libladder.so
fi

if [ -f /vendor/lib64/libladder.so ] && ! [ -f /home/anbox/tmp_vendor/lib64/libladder.so ]; then

    wget -O /home/anbox/tmp_vendor/lib64/libladder.so \
        https://github.com/GS290-dev/gigaset_gs290_dump/raw/full_k63v2_64_bsp-user-10-QP1A.190711.020-1597810494-release-keys/vendor/lib64/libladder.so

fi

if [ -f /vendor/lib64/libmpvr.so ] && ! [ -f /home/anbox/tmp_vendor/lib64/libmpvr.so ]; then
    cp /vendor/lib64/libmpvr.so /home/anbox/tmp_vendor/lib64/libmpvr.so
fi
if [ -f /vendor/lib/libmpvr.so ] && ! [ -f /home/anbox/tmp_vendor/lib/libmpvr.so ]; then
    cp /vendor/lib/libmpvr.so /home/anbox/tmp_vendor/lib/libmpvr.so
fi

sed -i "s/-service/-service --desktop_file_hint=unity8.desktop/" \
    /home/anbox/tmp_vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc

umount /home/anbox/tmp_vendor && rmdir /home/anbox/tmp_vendor

####

echo "Geting latest lxc config"

mkdir -p /var/lib/lxc/anbox

rm -f /var/lib/lxc/anbox/config*

LXC_VERSION="\$(lxc-info --version)"

if [ "\${LXC_VERSION%%.*}" -gt 2 ]; then
    export LXC_CONFIG_URL="https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/lxc-configs/config_2"
else
    export LXC_CONFIG_URL='https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/lxc-configs/config_1'
fi

wget -o /var/lib/lxc/anbox/config "\${LXC_CONFIG_URL}"

sed -i "s/LXCARCH/"${UNAME_ARCH}"/" /var/lib/lxc/anbox/config


wget -O /var/lib/lxc/anbox/config_nodes \
    https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/lxc-configs/config_nodes

if [ ! -e /dev/hwbinder ]; then
    sed -i "/host_hwbinder/d" /var/lib/lxc/anbox/config_nodes
fi

if ! grep -q "module-native-protocol-unix auth-anonymous=1" /etc/pulse/touch-android9.pa; then
    echo "Pulseaudio config patching..."
    cp /etc/pulse/touch-android9.pa /etc/pulse/touch-android9.pa.bak
    sed -i "s/module-native-protocol-unix/module-native-protocol-unix auth-anonymous=1/" /etc/pulse/touch-android9.pa
fi

if [ ! -f /etc/gbinder.d/anbox.conf ]; then
    echo "Adding gbinder config"
    mkdir -p /etc/gbinder.d
    wget -O /etc/gbinder.d/anbox.conf \
        https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/gbinder/anbox.conf
fi

mount -o remount,ro /

echo "Going back to phablet user"
EOF

cd /home/phablet

echo "Restarting Pulseaudio service"

initctl --user stop pulseaudio
initctl --user start pulseaudio

echo "Installing Finished!"
echo 'Run anbox container with "sudo /home/anbox/run-container.sh" on terminal'
echo 'Stop anbox container with "sudo /home/anbox/stop-container.sh" on terminal'
