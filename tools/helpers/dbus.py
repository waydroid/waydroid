import logging
import tools.config
import os
from tools.helpers.instance import get_container_dbus_name


def setup_policy(args):
    dbus_conf_dir = "/usr/share/dbus-1/system.d"
    if not os.path.exists(dbus_conf_dir):
        raise RuntimeError("DBUS configuration directory does not exist")

    target = f"{dbus_conf_dir}/{get_container_dbus_name()}.conf"
    source = f"{tools.config.tools_src}/dbus/id.waydro.Container.conf"

    if os.path.exists(target):
        logging.info(f"DBUS policy file already exists at {target}")
        return

    with open(source, "r") as f:
        content = f.read().replace("id.waydro.Container", get_container_dbus_name())
    
    with open(target, "w") as f:
        f.write(content)

    logging.info(f"DBUS policy file written to {target}")
    
    