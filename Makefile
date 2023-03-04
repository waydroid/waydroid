PREFIX := /usr

USE_SYSTEMD ?= 1
USE_DBUS_ACTIVATION ?= 1
USE_NFTABLES ?= 0

WAYDROID_DIR := $(PREFIX)/lib/waydroid
BIN_DIR := $(PREFIX)/bin
CONF_DIR := $(PREFIX)/etc/waydroid
APPS_DIR := $(PREFIX)/share/applications
METAINFO_DIR := $(PREFIX)/share/metainfo
ICONS_DIR := $(PREFIX)/share/icons
SYSD_DIR := $(PREFIX)/lib/systemd/system
DBUS_DIR := $(PREFIX)/share/dbus-1
POLKIT_DIR := $(PREFIX)/share/polkit-1
APPARMOR_DIR := /etc/apparmor.d

INSTALL_WAYDROID_DIR := $(DESTDIR)$(WAYDROID_DIR)
INSTALL_BIN_DIR := $(DESTDIR)$(BIN_DIR)
INSTALL_CONF_DIR := $(DESTDIR)$(CONF_DIR)
INSTALL_APPS_DIR := $(DESTDIR)$(APPS_DIR)
INSTALL_METAINFO_DIR := $(DESTDIR)$(METAINFO_DIR)
INSTALL_ICONS_DIR := $(DESTDIR)$(ICONS_DIR)
INSTALL_SYSD_DIR := $(DESTDIR)$(SYSD_DIR)
INSTALL_DBUS_DIR := $(DESTDIR)$(DBUS_DIR)
INSTALL_POLKIT_DIR := $(DESTDIR)$(POLKIT_DIR)
INSTALL_APPARMOR_DIR := $(DESTDIR)$(APPARMOR_DIR)

build:
	@echo "Nothing to build, run 'make install' to copy the files!"


copy:
	install -d $(INSTALL_WAYDROID_DIR) $(INSTALL_BIN_DIR) $(INSTALL_DBUS_DIR)/system.d $(INSTALL_POLKIT_DIR)/actions
	install -d $(INSTALL_APPS_DIR) $(INSTALL_METAINFO_DIR) $(INSTALL_ICONS_DIR)/hicolor/512x512/apps
	cp -a data tools waydroid.py $(INSTALL_WAYDROID_DIR)
	ln -sf $(WAYDROID_DIR)/waydroid.py $(INSTALL_BIN_DIR)/waydroid
	ln -sf $(WAYDROID_DIR)/data/AppIcon.png $(INSTALL_ICONS_DIR)/hicolor/512x512/apps/waydroid.png
	mv $(INSTALL_WAYDROID_DIR)/data/*.desktop $(INSTALL_APPS_DIR)
	mv $(INSTALL_WAYDROID_DIR)/data/*.metainfo.xml $(INSTALL_METAINFO_DIR)
	cp dbus/id.waydro.Container.conf $(INSTALL_DBUS_DIR)/system.d/
	cp dbus/id.waydro.Container.policy $(INSTALL_POLKIT_DIR)/actions/


services:
	if [ $(USE_SYSTEMD) = 1 ]; then \
		install -d $(INSTALL_SYSD_DIR); \
		cp service_managers/systemd/waydroid-container.service $(INSTALL_SYSD_DIR); \
	fi


reconfigure: copy
	if [ $(USE_NFTABLES) = 1 ]; then \
		sed '/LXC_USE_NFT=/ s/false/true/' -i $(INSTALL_WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	elif [ $(USE_NFTABLES) = 0 ]; then \
		sed '/LXC_USE_NFT=/ s/true/false/' -i $(INSTALL_WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	fi
	cp -t $(INSTALL_CONF_DIR)/ data/configs/lxc.conf 
	mkdir -p $(INSTALL_CONF_DIR)/nftables.d
	cp -t $(INSTALL_CONF_DIR)/ data/configs/nftables.d/ipv6.nft data/configs/nftables.d/base.nft


install: copy services reconfigure
	if [ $(USE_DBUS_ACTIVATION) = 1 ]; then \
		install -d $(INSTALL_DBUS_DIR)/system-services; \
		cp dbus/id.waydro.Container.service $(INSTALL_DBUS_DIR)/system-services/; \
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

clean:
	@echo "Will remove $(INSTALL_WAYDROID_DIR)/ $(INSTALL_CONF_DIR) $(INSTALL_APPS_DIR)/waydroid.desktop $(INSTALL_METAINFO_DIR)/id.waydro.waydroid.metainfo.xml $(INSTALL_BIN_DIR)/waydroid $(INSTALL_APPARMOR_DIR)"
	@#echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	rm -rf $(INSTALL_WAYDROID_DIR) $(INSTALL_CONF_DIR) $(INSTALL_APPARMOR_DIR)
	rm -f $(INSTALL_APPS_DIR)/waydroid.desktop $(INSTALL_METAINFO_DIR)/id.waydro.waydroid.metainfo.xml
	[ -L $(INSTALL_BIN_DIR)/waydroid ] && unlink $(INSTALL_BIN_DIR)/waydroid

