#!/bin/sh
# LXC post-stop hook.
#
# waydroid manages the container lifecycle itself, so LXC must not
# automatically respawn the container when the guest reboots or crashes.
# LXC suppresses that respawn when the post-stop hook exits non-zero.
#
# We only need to suppress it on a reboot; on a normal shutdown we exit 0
# so that a routine `waydroid session stop` doesn't log a spurious
# "Failed to run lxc.hook.post-stop" error (the previous no-op hook was
# `/dev/null`, which is not executable and therefore failed on every stop).
#
# LXC_TARGET is "stop" for a shutdown and "reboot" for a reboot. Default to
# suppressing the respawn for any other/unset value to preserve the old
# always-non-zero behaviour.
[ "$LXC_TARGET" = "stop" ] && exit 0
exit 1
