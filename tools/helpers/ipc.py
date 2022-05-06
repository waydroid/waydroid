# Copyright 2022 Alessandro Astone
# SPDX-License-Identifier: GPL-3.0-or-later

# Currently implemented as FIFO
import os

BASE_DIR = "/var/run/"

def listen(channel):
    pipe = BASE_DIR + "waydroid-" + channel
    if not os.path.exists(pipe):
        os.mkfifo(pipe)
    with open(pipe) as fifo:
        while True:
            data = fifo.read()
            if len(data) != 0:
                return data

def notify(channel, msg):
    pipe = BASE_DIR + "waydroid-" + channel
    try:
        fd = os.open(pipe, os.O_WRONLY | os.O_NONBLOCK)
        with os.fdopen(fd, "w") as fifo:
            fifo.write(msg)
    except Exception:
        pass
