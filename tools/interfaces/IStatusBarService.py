import gbinder
import logging
import time
from tools import helpers


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
    serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)
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
