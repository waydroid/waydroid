import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "lineageos.waydroid.IHardware"
SERVICE_NAME = "waydroidhardware"

TRANSACTION_enableNFC = 1
TRANSACTION_enableBluetooth = 2
TRANSACTION_suspend = 3
TRANSACTION_reboot = 4
TRANSACTION_upgrade = 5
TRANSACTION_upgrade2 = 6

def add_service(args, enableNFC, enableBluetooth, suspend, reboot, upgrade):
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
        if code == TRANSACTION_enableNFC:
            status, arg1 = reader.read_int32()
            ret = enableNFC(arg1 != 0)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        elif code == TRANSACTION_enableBluetooth:
            status, arg1 = reader.read_int32()
            ret = enableBluetooth(arg1 != 0)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        elif code == TRANSACTION_suspend:
            suspend()
            local_response.append_int32(0)
        elif code == TRANSACTION_reboot:
            reboot()
            local_response.append_int32(0)
        elif code == TRANSACTION_upgrade:
            arg1 = reader.read_string16()
            status, arg2 = reader.read_int32()
            arg3 = reader.read_string16()
            status, arg4 = reader.read_int32()
            upgrade(arg1, arg2, arg3, arg4)
            local_response.append_int32(0)
        elif code == TRANSACTION_upgrade2:
            arg1 = reader.read_string16()
            status, arg2 = reader.read_int64()
            arg3 = reader.read_string16()
            status, arg4 = reader.read_int64()
            upgrade(arg1, arg2, arg3, arg4)
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
                args.hardwareLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.hardwareLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.hardwareLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
