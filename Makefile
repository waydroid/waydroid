PREFIX := /usr

USE_SYSTEMD ?= 1
USE_DBUS_ACTIVATION ?= 1
USE_NFTABLES ?= 0

SYSCONFDIR := /etc
WAYDROID_DIR := $(PREFIX)/lib/waydroid
BIN_DIR := $(PREFIX)/bin
APPS_DIR := $(PREFIX)/share/applications
APPS_DIRECTORY_DIR := $(PREFIX)/share/desktop-directories
APPS_MENU_DIR := $(SYSCONFDIR)/xdg/menus/applications-merged
METAINFO_DIR := $(PREFIX)/share/metainfo
ICONS_DIR := $(PREFIX)/share/icons
SYSD_DIR := $(PREFIX)/lib/systemd/system
DBUS_DIR := $(PREFIX)/share/dbus-1
POLKIT_DIR := $(PREFIX)/share/polkit-1
APPARMOR_DIR := $(SYSCONFDIR)/apparmor.d

INSTALL_WAYDROID_DIR := $(DESTDIR)$(WAYDROID_DIR)
INSTALL_BIN_DIR := $(DESTDIR)$(BIN_DIR)
INSTALL_APPS_DIR := $(DESTDIR)$(APPS_DIR)
INSTALL_APPS_DIRECTORY_DIR := $(DESTDIR)$(APPS_DIRECTORY_DIR)
INSTALL_APPS_MENU_DIR := $(DESTDIR)$(APPS_MENU_DIR)
INSTALL_METAINFO_DIR := $(DESTDIR)$(METAINFO_DIR)
INSTALL_ICONS_DIR := $(DESTDIR)$(ICONS_DIR)
INSTALL_SYSD_DIR := $(DESTDIR)$(SYSD_DIR)
INSTALL_DBUS_DIR := $(DESTDIR)$(DBUS_DIR)
INSTALL_POLKIT_DIR := $(DESTDIR)$(POLKIT_DIR)
INSTALL_APPARMOR_DIR := $(DESTDIR)$(APPARMOR_DIR)

build:
	@echo "Nothing to build, run 'make install' to copy the files!"

install:
	install -d $(INSTALL_WAYDROID_DIR) $(INSTALL_BIN_DIR) $(INSTALL_DBUS_DIR)/system.d $(INSTALL_POLKIT_DIR)/actions
	install -d $(INSTALL_APPS_DIR) $(INSTALL_METAINFO_DIR) $(INSTALL_ICONS_DIR)/hicolor/512x512/apps
	install -d $(INSTALL_APPS_DIRECTORY_DIR) $(INSTALL_APPS_MENU_DIR)
	cp -a data tools waydroid.py $(INSTALL_WAYDROID_DIR)
	ln -sf $(WAYDROID_DIR)/waydroid.py $(INSTALL_BIN_DIR)/waydroid
	mv $(INSTALL_WAYDROID_DIR)/data/AppIcon.png $(INSTALL_ICONS_DIR)/hicolor/512x512/apps/waydroid.png
	mv $(INSTALL_WAYDROID_DIR)/data/*.desktop $(INSTALL_APPS_DIR)
	mv $(INSTALL_WAYDROID_DIR)/data/*.menu $(INSTALL_APPS_MENU_DIR)
	mv $(INSTALL_WAYDROID_DIR)/data/*.directory $(INSTALL_APPS_DIRECTORY_DIR)
	mv $(INSTALL_WAYDROID_DIR)/data/*.metainfo.xml $(INSTALL_METAINFO_DIR)
	cp dbus/id.waydro.Container.conf $(INSTALL_DBUS_DIR)/system.d/
	cp dbus/id.waydro.Container.policy $(INSTALL_POLKIT_DIR)/actions/
	if [ $(USE_DBUS_ACTIVATION) = 1 ]; then \
		install -d $(INSTALL_DBUS_DIR)/system-services; \
		cp dbus/id.waydro.Container.service $(INSTALL_DBUS_DIR)/system-services/; \
	fi
	if [ $(USE_SYSTEMD) = 1 ]; then \
		install -d $(INSTALL_SYSD_DIR); \
		cp systemd/waydroid-container.service $(INSTALL_SYSD_DIR); \
	fi
	if [ $(USE_NFTABLES) = 1 ]; then \
		sed '/LXC_USE_NFT=/ s/false/true/' -i $(INSTALL_WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	fi

install_apparmor:
	install -d $(INSTALL_APPARMOR_DIR) $(INSTALL_APPARMOR_DIR)/lxc
	mkdir -p $(INSTALL_APPARMOR_DIR)/local/
	touch $(INSTALL_APPARMOR_DIR)/local/adbd
	touch $(INSTALL_APPARMOR_DIR)/local/android_app
	touch $(INSTALL_APPARMOR_DIR)/local/lxc-waydroid
	cp -f data/configs/apparmor_profiles/adbd $(INSTALL_APPARMOR_DIR)/adbd
	cp -f data/configs/apparmor_profiles/android_app $(INSTALL_APPARMOR_DIR)/android_app
	cp -f data/configs/apparmor_profiles/lxc-waydroid $(INSTALL_APPARMOR_DIR)/lxc/lxc-waydroid
	# Load the profiles if not just packaging
	if [ -z $(DESTDIR) ] && { aa-enabled --quiet || systemctl is-active -q apparmor; } 2>/dev/null; then \
		apparmor_parser -r -T -W "$(INSTALL_APPARMOR_DIR)/adbd"; \
		apparmor_parser -r -T -W "$(INSTALL_APPARMOR_DIR)/android_app"; \
		apparmor_parser -r -T -W "$(INSTALL_APPARMOR_DIR)/lxc/lxc-waydroid"; \
	fi
