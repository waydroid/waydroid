#!/bin/bash

WAYDROID_PATH=/var/lib/lxc/waydroid

. /usr/share/waydroid/generate-props.sh

if [ -f "${WAYDROID_PATH}/anbox.prop" ]; then
    exit 0
fi

echo "${GRALLOC_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${EGL_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${MEDIA_PROFILES_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${CCODEC_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${EXT_LIB_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${VULKAN_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${DPI_PROP}" >> ${WAYDROID_PATH}/anbox.prop
echo "${GLES_VER_PROP}" >> ${WAYDROID_PATH}/anbox.prop

# FIXME
echo "anbox.xdg_runtime_dir=/run/user/32011" >> ${WAYDROID_PATH}/anbox.prop
echo "anbox.wayland_display=wayland-0" >> ${WAYDROID_PATH}/anbox.prop
echo "anbox.pulse_runtime_path=/run/user/32011/pulse" >> ${WAYDROID_PATH}/anbox.prop
echo "anbox.display_height_padding=200" >> ${WAYDROID_PATH}/anbox.prop

# TODO: Drop this
echo "anbox.active_apps=full" >> ${WAYDROID_PATH}/anbox.prop

