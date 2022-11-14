PREFIX := /usr

USE_SYSTEMD ?= 1
USE_NFTABLES ?= 0

WAYDROID_DIR := $(PREFIX)/lib/waydroid
BIN_DIR := $(PREFIX)/bin
APPS_DIR := $(PREFIX)/share/applications
METAINFO_DIR := $(PREFIX)/share/metainfo
SYSD_DIR := $(PREFIX)/lib/systemd/system
APPARMOR_DIR := /etc/apparmor.d

INSTALL_WAYDROID_DIR := $(DESTDIR)$(WAYDROID_DIR)
INSTALL_BIN_DIR := $(DESTDIR)$(BIN_DIR)
INSTALL_APPS_DIR := $(DESTDIR)$(APPS_DIR)
INSTALL_METAINFO_DIR := $(DESTDIR)$(METAINFO_DIR)
INSTALL_SYSD_DIR := $(DESTDIR)$(SYSD_DIR)
INSTALL_APPARMOR_DIR := $(DESTDIR)$(APPARMOR_DIR)

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

install_apparmor:
	install -d $(INSTALL_APPARMOR_DIR) $(INSTALL_APPARMOR_DIR)/lxc
	cp -f data/configs/apparmor_profiles/adbd $(INSTALL_APPARMOR_DIR)/adbd
	cp -f data/configs/apparmor_profiles/android_app $(INSTALL_APPARMOR_DIR)/android_app
	cp -f data/configs/apparmor_profiles/lxc-waydroid $(INSTALL_APPARMOR_DIR)/lxc/lxc-waydroid
	# Load the profiles if not just packaging
	if [ -z $(DESTDIR) ] && { aa-enabled --quiet || systemctl is-active -q apparmor; } 2>/dev/null; then \
		apparmor_parser -r -T -W "$(INSTALL_APPARMOR_DIR)/adbd"; \
		apparmor_parser -r -T -W "$(INSTALL_APPARMOR_DIR)/android_app"; \
		apparmor_parser -r -T -W "$(INSTALL_APPARMOR_DIR)/lxc/lxc-waydroid"; \
	fi
