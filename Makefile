PREFIX := /usr

USE_SYSTEMD ?= 1
USE_NFTABLES ?= 0

WAYDROID_DIR := $(PREFIX)/lib/waydroid
BIN_DIR := $(PREFIX)/bin
APPS_DIR := $(PREFIX)/share/applications
METAINFO_DIR := $(PREFIX)/share/metainfo
SYSD_DIR := $(PREFIX)/lib/systemd/system

INSTALL_WAYDROID_DIR := $(DESTDIR)$(WAYDROID_DIR)
INSTALL_BIN_DIR := $(DESTDIR)$(BIN_DIR)
INSTALL_APPS_DIR := $(DESTDIR)$(APPS_DIR)
INSTALL_METAINFO_DIR := $(DESTDIR)$(METAINFO_DIR)
INSTALL_SYSD_DIR := $(DESTDIR)$(SYSD_DIR)

build:
	@echo "Nothing to build, run 'make install' to copy the files!"

install:
	install -d $(INSTALL_WAYDROID_DIR) $(INSTALL_BIN_DIR) $(INSTALL_APPS_DIR) $(INSTALL_METAINFO_DIR)
	cp -a data tools waydroid.py $(INSTALL_WAYDROID_DIR)
	ln -sf $(WAYDROID_DIR)/waydroid.py $(INSTALL_BIN_DIR)/waydroid
	mv $(INSTALL_WAYDROID_DIR)/data/*.desktop $(INSTALL_APPS_DIR)
	mv $(INSTALL_WAYDROID_DIR)/data/*.metainfo.xml $(INSTALL_METAINFO_DIR)
	if [ $(USE_SYSTEMD) = 1 ]; then \
		install -d $(INSTALL_SYSD_DIR); \
		cp systemd/waydroid-container.service $(INSTALL_SYSD_DIR); \
	fi
	if [ $(USE_NFTABLES) = 1 ]; then \
		sed '/LXC_USE_NFT=/ s/false/true/' -i $(INSTALL_WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	fi

apparmor:
	cp -f data/configs/adbd /etc/apparmor.d/adbd
	apparmor_parser -r /etc/apparmor.d/adbd
	cp -f data/configs/android_app /etc/apparmor.d/android_app
	apparmor_parser -r /etc/apparmor.d/android_app
	cp -f data/configs/lxc-waydroid /etc/apparmor.d/lxc/lxc-waydroid
	apparmor_parser -r /etc/apparmor.d/lxc/lxc-waydroid
	sed --sandbox -i "s/lxc.aa_profile = unconfined/lxc.aa_profile = lxc-waydroid/g;" /var/lib/waydroid/lxc/waydroid/config
	sed --sandbox -i "s/lxc.apparmor.profile = unconfined/lxc.apparmor.profile = lxc-waydroid/g;" /var/lib/waydroid/lxc/waydroid/config

