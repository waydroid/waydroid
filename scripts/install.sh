#!/bin/bash

SUPPORTED_ARCHS="x86_64 aarch64 armv8l"
UNAME_ARCH=`uname -m`
export GIT_REPO="https://github.com/calebccff/anbox-halium/raw/lineage-17.1"

for a in $SUPPORTED_ARCHS; do
    if [ "$UNAME_ARCH" == "$a" ]; then
        ARCH="$a"
    fi
done
if [ -z ${ARCH} ]; then
    echo "ERROR: Your system with arch $UNAME_ARCH is not supported"
    exit
fi
if [ "$UNAME_ARCH" == "aarch64" ]; then
    ARCH="arm64"
fi
if [ "$UNAME_ARCH" == "armv8l" ]; then
    ARCH="arm64"
fi
if [ "$UNAME_ARCH" == "armv7l" ]; then
    ARCH="arm"
fi
if [ "$UNAME_ARCH" == "i386" ]; then
    ARCH="x86"
fi
if [ "$UNAME_ARCH" == "i686" ]; then
    ARCH="x86"
fi

export ARCH

echo "Generating device properties"
rm -f generate-props.sh
wget "$GIT_REPO/scripts/generate-props.sh"
chmod +x generate-props.sh
set -a
. generate-props.sh
set +a

. /etc/os-release

rm -f anbox-distro-setup.sh
DISTRO="ut"
if [ "$NAME" == "postmarketOS" ]; then
    DISTRO="pmos"
fi

wget "$GIT_REPO/scripts/install-$DISTRO.sh" -O anbox-distro-setup.sh
chmod +x anbox-distro-setup.sh
./anbox-distro-setup.sh

echo "Installing Finished!"
echo "Run anbox container with \"sudo /home/anbox/run-container.sh\" on terminal"
echo "Stop anbox container with \"sudo /home/anbox/stop-container.sh\" on terminal"
