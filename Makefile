PREFIX := /usr

USE_SYSTEMD ?= 1
USE_DBUS_ACTIVATION ?= 1
USE_NFTABLES ?= 0

SYSCONFDIR := /etc
ANDROMEDA_DIR := $(PREFIX)/lib/andromeda
BIN_DIR := $(PREFIX)/bin
APPS_DIR := $(PREFIX)/share/applications
APPS_DIRECTORY_DIR := $(PREFIX)/share/desktop-directories
APPS_MENU_DIR := $(SYSCONFDIR)/xdg/menus/applications-merged
ICONS_DIR := $(PREFIX)/share/icons
SYSD_DIR := $(PREFIX)/lib/systemd/system
SYSD_USER_DIR := $(PREFIX)/lib/systemd/user
DBUS_DIR := $(PREFIX)/share/dbus-1
POLKIT_DIR := $(PREFIX)/share/polkit-1
LIBEXEC_DIR := $(PREFIX)/libexec

INSTALL_ANDROMEDA_DIR := $(DESTDIR)$(ANDROMEDA_DIR)
INSTALL_BIN_DIR := $(DESTDIR)$(BIN_DIR)
INSTALL_APPS_DIR := $(DESTDIR)$(APPS_DIR)
INSTALL_APPS_DIRECTORY_DIR := $(DESTDIR)$(APPS_DIRECTORY_DIR)
INSTALL_APPS_MENU_DIR := $(DESTDIR)$(APPS_MENU_DIR)
INSTALL_ICONS_DIR := $(DESTDIR)$(ICONS_DIR)
INSTALL_SYSD_DIR := $(DESTDIR)$(SYSD_DIR)
INSTALL_SYSD_USER_DIR := $(DESTDIR)$(SYSD_USER_DIR)
INSTALL_DBUS_DIR := $(DESTDIR)$(DBUS_DIR)
INSTALL_POLKIT_DIR := $(DESTDIR)$(POLKIT_DIR)
INSTALL_LIBEXEC_DIR := $(DESTDIR)$(LIBEXEC_DIR)

build:
	@echo "Nothing to build, run 'make install' to copy the files!"

install:
	install -d $(INSTALL_ANDROMEDA_DIR) $(INSTALL_BIN_DIR) $(INSTALL_DBUS_DIR)/system.d $(INSTALL_POLKIT_DIR)/actions
	install -d $(INSTALL_APPS_DIR) $(INSTALL_ICONS_DIR)/hicolor/scalable/apps $(INSTALL_APPS_DIRECTORY_DIR) $(INSTALL_APPS_MENU_DIR) $(INSTALL_LIBEXEC_DIR)
	cp -a data tools andromeda.py $(INSTALL_ANDROMEDA_DIR)
	ln -sf $(ANDROMEDA_DIR)/andromeda.py $(INSTALL_BIN_DIR)/andromeda
	mv $(INSTALL_ANDROMEDA_DIR)/data/AppIcon.svg $(INSTALL_ICONS_DIR)/hicolor/scalable/apps/andromeda.svg
	mv $(INSTALL_ANDROMEDA_DIR)/data/*.desktop $(INSTALL_APPS_DIR)
	mv $(INSTALL_ANDROMEDA_DIR)/data/*.menu $(INSTALL_APPS_MENU_DIR)
	mv $(INSTALL_ANDROMEDA_DIR)/data/*.directory $(INSTALL_APPS_DIRECTORY_DIR)
	cp dbus/io.furios.Andromeda.Container.conf $(INSTALL_DBUS_DIR)/system.d/
	cp dbus/io.furios.Andromeda.Notification.conf $(INSTALL_DBUS_DIR)/system.d/
	cp dbus/io.furios.Andromeda.StateChange.conf $(INSTALL_DBUS_DIR)/system.d/
	if [ $(USE_DBUS_ACTIVATION) = 1 ]; then \
		install -d $(INSTALL_DBUS_DIR)/system-services; \
		install -d $(INSTALL_DBUS_DIR)/services/; \
		cp dbus/io.furios.Andromeda.Container.service $(INSTALL_DBUS_DIR)/system-services/; \
		cp dbus/io.furios.Andromeda.Notification.service $(INSTALL_DBUS_DIR)/system-services/; \
	fi
	if [ $(USE_SYSTEMD) = 1 ]; then \
		install -d $(INSTALL_SYSD_DIR) $(INSTALL_SYSD_USER_DIR); \
		cp systemd/andromeda-container.service $(INSTALL_SYSD_DIR); \
		cp systemd/andromeda-notification-server.service $(INSTALL_SYSD_DIR); \
		cp systemd/andromeda-statechange-server.service $(INSTALL_SYSD_DIR); \
		cp systemd/andromeda-session.service $(INSTALL_SYSD_USER_DIR); \
	fi
	if [ $(USE_NFTABLES) = 1 ]; then \
		sed '/LXC_USE_NFT=/ s/false/true/' -i $(INSTALL_ANDROMEDA_DIR)/data/scripts/andromeda-net.sh; \
	fi
