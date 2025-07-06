import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "lineageos.waydroid.IUserMonitor"
SERVICE_NAME = "waydroidusermonitor"

TRANSACTION_userUnlocked = 1
TRANSACTION_packageStateChanged = 2

PACKAGE_ADDED = 0;
PACKAGE_REMOVED = 1;
PACKAGE_UPDATED = 2;

def add_service(args, userUnlocked, packageStateChanged):
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
        if code == TRANSACTION_userUnlocked:
            status, arg1 = reader.read_int32()
            userUnlocked(arg1)
            local_response.append_int32(0)
        elif code == TRANSACTION_packageStateChanged:
            status, arg1 = reader.read_int32()
            arg2 = reader.read_string16()
            status, arg3 = reader.read_int32()
            packageStateChanged(arg1, arg2, arg3)
            local_response.append_int32(0)
        else:
            return local_response, -99999 # Some error unknown to binder to force a RemoteException

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.userMonitorLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.userMonitorLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.userMonitorLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))

