# Makefile for VkLayer_waydroid_compat.so
#
# Build the Vulkan compatibility layer as a shared library.
#
# For native (host) build:
#   make
#
# For Android cross-compile (requires Android NDK):
#   make CC=aarch64-linux-android33-clang \
#        CFLAGS="-DANDROID -fPIC" \
#        LDFLAGS="-shared -llog"
#
# The resulting .so should be placed at:
#   /var/lib/waydroid/overlay/vendor/lib64/vulkan/VkLayer_waydroid_compat.so

CC       ?= gcc
CFLAGS   ?= -O2 -Wall -Wextra -fPIC -std=c11
LDFLAGS  ?= -shared

# Vulkan SDK headers path (adjust if needed)
VULKAN_INCLUDE ?= /usr/include

TARGET   = VkLayer_waydroid_compat.so
SRC      = VkLayer_waydroid_compat.c

.PHONY: all clean install

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -I$(VULKAN_INCLUDE) $(SRC) -o $(TARGET) $(LDFLAGS)

clean:
	rm -f $(TARGET)

install: $(TARGET)
	@echo "Installing to overlay path..."
	install -D -m 644 $(TARGET) \
		/var/lib/waydroid/overlay/vendor/lib64/vulkan/$(TARGET)
	install -D -m 644 VkLayer_waydroid_compat.json \
		/var/lib/waydroid/overlay/vendor/lib64/vulkan/VkLayer_waydroid_compat.json
	@echo "Done. Restart waydroid to activate."
