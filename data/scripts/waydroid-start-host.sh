#!/bin/sh
# LXC start-host hook.
#
# 32-bit bionic can't handle pids/tids above 65535, so cap pid_max in the
# container's pid namespace. That is only per namespace since Linux 6.14;
# on older kernels the write would change the host's value.
# Always exit 0: a failing start-host hook aborts the container start.
v=$(uname -r)
major=${v%%.*}
minor=${v#*.}
minor=${minor%%[!0-9]*}
if [ "$major" -gt 6 ] || { [ "$major" -eq 6 ] && [ "$minor" -ge 14 ]; }; then
	nsenter -t "$LXC_PID" -p -- sh -c 'echo 32768 > /proc/sys/kernel/pid_max' ||
		echo "waydroid: could not cap pid_max in the container" >&2
fi
exit 0
