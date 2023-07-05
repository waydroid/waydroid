import gbinder
import logging
import time
from tools import helpers
from gi.repository import GLib
import signal


INTERFACE = "com.android.internal.statusbar.IStatusBarService"
SERVICE_NAME = "statusbar"

TRANSACTION_expand = 1
TRANSACTION_collapse = 2

class IStatusBarService:
    def __init__(self, remote):
        self.client = gbinder.Client(remote, INTERFACE)

    def expand(self):
        request = self.client.new_request()
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_expand, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception != 0:
                logging.error("Failed with code: {}".format(exception))

    def collapse(self):
        request = self.client.new_request()
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_collapse, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception != 0:
                logging.error("Failed with code: {}".format(exception))

def get_service(args):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    if not serviceManager.is_present():
        logging.info("Waiting for binder Service Manager...")
        if not wait_for_manager(serviceManager):
            logging.error("Service Manager never appeared")
            return None

    tries = 1000

    remote, status = serviceManager.get_service_sync(SERVICE_NAME)
    while(not remote):
        if tries > 0:
            logging.warning(
                "Failed to get service {}, trying again...".format(SERVICE_NAME))
            time.sleep(1)
            remote, status = serviceManager.get_service_sync(SERVICE_NAME)
            tries = tries - 1
        else:
            return None

    return IStatusBarService(remote)

# Like ServiceManager.wait() but can be interrupted
def wait_for_manager(sm):
    mainloop = GLib.MainLoop()
    hndl = sm.add_presence_handler(lambda: mainloop.quit() if sm.is_present() else None)
    GLib.timeout_add_seconds(60, lambda: mainloop.quit())
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, lambda _: mainloop.quit(), None)
    mainloop.run()
    sm.remove_handler(hndl)
    if not sm.is_present():
        return False
    return True
