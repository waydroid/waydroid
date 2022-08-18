PREFIX := /usr

USE_SYSTEMD ?= 1
USE_NFTABLES ?= 0

WAYDROID_DIR := $(DESTDIR)$(PREFIX)/lib/waydroid
BIN_DIR := $(DESTDIR)$(PREFIX)/bin
APPS_DIR := $(DESTDIR)$(PREFIX)/share/applications
METAINFO_DIR := $(DESTDIR)$(PREFIX)/share/metainfo
SYSD_DIR := $(DESTDIR)$(PREFIX)/lib/systemd/system

build:
	@echo "Nothing to build, run 'make install' to copy the files!"

install:
	install -d $(WAYDROID_DIR) $(BIN_DIR) $(APPS_DIR) $(METAINFO_DIR)
	cp -a data tools waydroid.py $(WAYDROID_DIR)
	ln -srf $(WAYDROID_DIR)/waydroid.py $(BIN_DIR)/waydroid
	mv $(WAYDROID_DIR)/data/*.desktop $(APPS_DIR)
	mv $(WAYDROID_DIR)/data/*.metainfo.xml $(METAINFO_DIR)
	if [ $(USE_SYSTEMD) = 1 ]; then \
		install -d $(SYSD_DIR); \
		cp systemd/waydroid-container.service $(SYSD_DIR); \
	fi
	if [ $(USE_NFTABLES) = 1 ]; then \
		sed '/LXC_USE_NFT=/ s/false/true/' -i $(WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	fi
