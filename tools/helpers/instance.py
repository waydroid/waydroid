from tools.helpers.arguments import arguments

INSTANCE_NAME = arguments("").instance

def get_container_dbus_name():
    return f"id.waydro.Container{get_suffix()}"

def get_container_name():
    return f"waydroid"

def get_session_dbus_name():
    return f"id.waydro.Session{get_suffix()}"

def get_work_dir():
    return f"/var/lib/waydroid{get_suffix()}"

def get_data_dir():
    return f"/waydroid{get_suffix()}/data"

def get_inet_name():
    return f"waydroid{get_suffix_dash()}"

def get_suffix():
    return f".{INSTANCE_NAME}" if INSTANCE_NAME else ""

def get_suffix_dash():
    return f"-{INSTANCE_NAME}" if INSTANCE_NAME else ""    

def get_binderfs_dir():
    return f"/dev/binderfs{get_suffix_dash()}"

def wrap_suffix(input):
    return f"{input}{get_suffix_dash()}"