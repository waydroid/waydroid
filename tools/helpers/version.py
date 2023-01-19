import os

def versiontuple(v):
    return tuple(map(int, (v.split("."))))

def kernel_version():
    return tuple(map(int, os.uname().release.split(".", 2)[:2]))
