#!/bin/sh

if ! $(which getprop); then
    echo "getprop not found, assuming this is a mainline device"
    alias getprop=true
fi

find_hal ()
{
HAL_PROP=
for p in "ro.hardware.$1" "ro.hardware" "ro.product.board" "ro.arch" "ro.board.platform"; do
    if [ "$(getprop $p)" != "" ]; then
        for l in lib lib64; do
            HAL_FILE=/vendor/$l/hw/$1.$(getprop $p).so
            HAL_FILE_PATH=$(readlink -f $HAL_FILE)
            if [ -f "$HAL_FILE_PATH" ]; then
                HAL_PROP=$(echo $HAL_FILE |sed "s|.*$1.\(.*\).so|\1|")
                if [ "$HAL_PROP" != "" ]; then
                    break
                fi
            fi
        done
    fi
    if [ "$HAL_PROP" != "" ]; then
        break
    fi
done

echo $HAL_PROP
}

GRALLOC=$(find_hal gralloc)
if [ -z $GRALLOC ]; then
    GRALLOC="gbm"
    EGL_PROP="ro.hardware.egl=mesa"
    CCODEC_PROP="debug.stagefright.ccodec=0"
fi
GRALLOC_PROP="ro.hardware.gralloc=${GRALLOC}"

EGL=`getprop ro.hardware.egl`
if [ ! -z $EGL ]; then
    EGL_PROP="ro.hardware.egl=${EGL}"
fi

MEDIA_PROFILES=`getprop media.settings.xml`
if [ ! -z $MEDIA_PROFILES ]; then
    MEDIA_PROFILES_EXTRA=`echo ${MEDIA_PROFILES} | sed "s/vendor/vendor_extra/" | sed "s/odm/odm_extra/"`
    MEDIA_PROFILES_PROP="media.settings.xml=${MEDIA_PROFILES_EXTRA}"
fi

CCODEC=`getprop debug.stagefright.ccodec`
if [ ! -z $CCODEC ]; then
    CCODEC_PROP="debug.stagefright.ccodec=${CCODEC}"
fi

EXT_LIB=`getprop ro.vendor.extension_library`
if [ ! -z $EXT_LIB ]; then
    EXT_LIB_EXTRA=`echo ${EXT_LIB} | sed 's/vendor/vendor_extra/g'`
    EXT_LIB_PROP="ro.vendor.extension_library=${EXT_LIB_EXTRA}"
fi

#TODO: Add gbm vulkan or something
VULKAN=$(find_hal vulkan)
if [ ! -z $VULKAN ]; then
    VULKAN_PROP="ro.hardware.vulkan=${VULKAN}"
fi

#TODO: Better dpi detection
DPI=$(getprop ro.sf.lcd_density)
if [ -z $DPI ]; then
    if [ ! -z $GRID_UNIT_PX ]; then
        DPI=`echo $GRID_UNIT_PX | awk '{$1=int($1*20);printf $1}'`
    else
        DPI="420"
    fi
fi
DPI_PROP="ro.sf.lcd_density=${DPI}"

GLES_VER=$(getprop ro.opengles.version)
if [ -z $GLES_VER ]; then
    GLES_VER="196608"
fi
GLES_VER_PROP="ro.opengles.version=${GLES_VER}"

if [ ! -z $XDG_RUNTIME_DIR ]; then
    XDG_PROP="anbox.xdg_runtime_dir=${XDG_RUNTIME_DIR}"
fi

if [ ! -z $WAYLAND_DISPLAY ]; then
    WAYLAND_DISP_PROP="anbox.wayland_display=${WAYLAND_DISPLAY}"
fi

if [ ! -z $PULSE_RUNTIME_PATH ]; then
    PULSE_PROP="anbox.pulse_runtime_path=${PULSE_RUNTIME_PATH}"
else
    if [ -d "${XDG_RUNTIME_DIR}/pulse" ]; then
        PULSE_PROP="anbox.pulse_runtime_path=${XDG_RUNTIME_DIR}/pulse"
    fi
fi
