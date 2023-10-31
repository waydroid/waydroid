import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "lineageos.waydroid.IClipboard"
SERVICE_NAME = "waydroidclipboard"

TRANSACTION_sendClipboardData = 1
TRANSACTION_getClipboardData = 2

def add_service(args, sendClipboardData, getClipboardData):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    def response_handler(req, code, flags):
        logging.debug(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        local_response = response.new_reply()
        if code == TRANSACTION_sendClipboardData:
            arg1 = reader.read_string16()
            sendClipboardData(arg1)
            local_response.append_int32(0)
        elif code == TRANSACTION_getClipboardData:
            ret = getClipboardData()
            local_response.append_int32(0)
            local_response.append_string16(ret)
        else:
            return local_response, -99999 # Some error unknown to binder to force a RemoteException

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.clipboardLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.clipboardLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.clipboardLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
