# Copyright 2022 Alessandro Astone
# SPDX-License-Identifier: GPL-3.0-or-later

# Currently implemented as FIFO
import os

BASE_DIR = "/var/run/"

def pipe_for(channel):
    return BASE_DIR + "waydroid-" + channel

def read_one(channel):
    with open_channel(channel, "r", 1) as fifo:
        while True:
            data = fifo.read()
            if len(data) != 0:
                return data

def create_channel(channel):
    pipe = pipe_for(channel)
    if not os.path.exists(pipe):
        os.mkfifo(pipe)

def open_channel(channel, mode, buffering=0):
    return open(pipe_for(channel), mode, buffering)

def notify(channel, msg):
    try:
        fd = os.open(pipe_for(channel), os.O_WRONLY | os.O_NONBLOCK)
        with os.fdopen(fd, "w") as fifo:
            fifo.write(msg)
    except Exception:
        pass

def notify_blocking(channel, msg):
    with open_channel(channel, "w", 1) as channel:
        channel.write(msg)
