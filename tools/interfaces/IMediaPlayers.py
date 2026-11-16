import gbinder
import logging
from tools import helpers
from gi.repository import GLib

from tools.interfaces.IMediaPlayersCallback import IMediaPlayersCallback

INTERFACE = "lineageos.waydroid.IMediaPlayers"
SERVICE_NAME = "waydroidmediaplayers"

TRANSACTION_registerListener = 1
TRANSACTION_update = 2
TRANSACTION_remove = 3

kNullParcelableFlag = 0

class Status:
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2

def read_text(reader):
    # D-Bus strings can't hold NUL
    return (reader.read_string16() or "").replace("\0", "")

class Player:
    def __init__(self, reader):
        self.id = read_text(reader)
        self.package_name = read_text(reader)
        self.app_name = read_text(reader)
        self.title = read_text(reader)
        self.artist = read_text(reader)
        self.album = read_text(reader)
        _, self.duration_ms = reader.read_int64()
        _, self.status = reader.read_int32() # Parcel.writeByte() writes an int
        _, self.position_ms = reader.read_int64()
        _, self.speed = reader.read_float()
        _, self.actions = reader.read_int64()
        try:
            # bytes, so the host can tell an unchanged cover from a new one
            self.art = bytes(reader.read_byte_array())
        except ValueError: # gbinder can't return an empty or null array
            self.art = None

def add_service(args, registerListener, update, remove):
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
        if code == TRANSACTION_registerListener:
            remote = reader.read_object()
            registerListener(IMediaPlayersCallback(remote))
            local_response.append_int32(0)
        elif code == TRANSACTION_update:
            _, parcel_null_flag = reader.read_int32()
            if parcel_null_flag != kNullParcelableFlag:
                _, parcel_size = reader.read_int32()
                update(Player(reader))
        elif code == TRANSACTION_remove:
            remove(reader.read_string16())
        else:
            return local_response, -99999 # Some error unknown to binder to force a RemoteException

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.mediaPlayersLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.mediaPlayersLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.mediaPlayersLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
