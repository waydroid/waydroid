PREFIX := /usr

USE_SYSTEMD ?= 1
USE_S6 ?= 0
USE_NFTABLES ?= 0

WAYDROID_DIR := $(DESTDIR)$(PREFIX)/lib/waydroid
BIN_DIR := $(DESTDIR)$(PREFIX)/bin
CONF_DIR := $(DESTDIR)/etc/waydroid
APPS_DIR := $(DESTDIR)$(PREFIX)/share/applications
METAINFO_DIR := $(DESTDIR)$(PREFIX)/share/metainfo

SYSD_DIR := $(DESTDIR)$(PREFIX)/lib/systemd/system
S6_DIR := $(DESTDIR)$(PREFIX)/lib/systemd/system

build:
	@echo "Nothing to build, run 'make install' to copy the files!"


copy:
	install -d $(WAYDROID_DIR) $(BIN_DIR) $(APPS_DIR) $(METAINFO_DIR)
	cp -a data tools waydroid.py $(WAYDROID_DIR)
	ln -srf $(WAYDROID_DIR)/waydroid.py $(BIN_DIR)/waydroid
	mv $(WAYDROID_DIR)/data/*.desktop $(APPS_DIR)
	mv $(WAYDROID_DIR)/data/*.metainfo.xml $(METAINFO_DIR)


install: copy services reconfigure
	install -d ${CONF_DIR};
	cp -t ${CONF_DIR} config/lxc.conf config/nftables.rules;
	cp -t ${CONF_DIR} -r config/lxc.d;


services:
	@if [ $(USE_SYSTEMD) = 1 ]; then \
		install -d $(SYSD_DIR); \
		cp service_managers/systemd/waydroid-container.service $(SYSD_DIR); \
	fi
	@if [ $(USE_S6) = 1 ]; then \
		install -d $(S6_DIR); \
		cp -r service_managers/s6/* $(S6_DIR); \
	fi


reconfigure: copy
	@if [ $(USE_NFTABLES) = 1 ]; then \
		sed '/LXC_USE_NFT=/ s/false/true/' -i $(WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	elif [ $(USE_NFTABLES) = 0 ]; then \
		sed '/LXC_USE_NFT=/ s/true/false/' -i $(WAYDROID_DIR)/data/scripts/waydroid-net.sh; \
	fi

clean:
	@echo "Will remove $(WAYDROID_DIR)/ $(CONF_DIR) $(APPS_DIR)/waydroid.desktop $(METAINFO_DIR)/id.waydro.waydroid.metainfo.xml $(BIN_DIR)/waydroid"
	@#echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	rm -rf $(WAYDROID_DIR) $(CONF_DIR) 
	rm -f $(APPS_DIR)/waydroid.desktop $(METAINFO_DIR)/id.waydro.waydroid.metainfo.xml
	[ -L $(BIN_DIR)/waydroid ] && unlink $(BIN_DIR)/waydroid


