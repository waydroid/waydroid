import gbinder
import logging
from tools import helpers
from gi.repository import GLib

from tools.interfaces.INotificationCallback import INotificationCallback

# Wrapper around org.freedesktop.notifications
# This is preferred over org.freedesktop.portal.Notification,
# because the latter does not allow us to match any desktop file

INTERFACE = "lineageos.waydroid.INotifications"
SERVICE_NAME = "waydroidnotifications"

TRANSACTION_registerListener = 1
TRANSACTION_notify = 2
TRANSACTION_closeNotification = 3

kNullParcelableFlag = 0

ID_NONE = 0

class Urgency:
    LOW = 0
    NORMAL = 1
    CRITICAL = 2

class Action:
    def __init__(self, action_id, label):
        self.id = action_id
        self.label = label

class ImageData:
    def __init__(self, width, height, rowstride, has_alpha, data):
        self.width = width
        self.height = height
        self.rowstride = rowstride
        self.has_alpha = has_alpha
        self.data = data

def add_service(args, registerListener, notify, closeNotification):
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
            registerListener(INotificationCallback(remote))
            local_response.append_int32(0)
        elif code == TRANSACTION_notify:
            _, replaces_id = reader.read_int32()
            app_name = reader.read_string16()
            package_name = reader.read_string16()
            summary = reader.read_string16()
            body = reader.read_string16()
            actions = []
            _, actions_length = reader.read_int32()
            for _ in range(actions_length):
                _, parcel_null_flag = reader.read_int32()
                if parcel_null_flag != kNullParcelableFlag:
                    _, parcel_size = reader.read_int32()
                    actions.append(Action(reader.read_string16(), reader.read_string16()))
            image_data = None
            _, parcel_null_flag = reader.read_int32()
            if (parcel_null_flag != kNullParcelableFlag):
                _, parcel_size = reader.read_int32()
                image_data = ImageData(
                    reader.read_int32()[1],
                    reader.read_int32()[1],
                    reader.read_int32()[1],
                    reader.read_bool()[1],
                    reader.read_byte_array(),
                )
            category = reader.read_string16()
            _, suppress_sound = reader.read_bool()
            _, expire_timeout = reader.read_int32()
            _, resident = reader.read_bool()
            _, transient = reader.read_bool()
            _, urgency = reader.read_byte()
            notification_id = notify(replaces_id, app_name, package_name, summary, body, actions, image_data, category, suppress_sound, expire_timeout, resident, transient, urgency)
            local_response.append_int32(0)
            local_response.append_int32(notification_id)
        elif code == TRANSACTION_closeNotification:
            _, notification_id = reader.read_int32()
            closeNotification(notification_id)
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
                args.notificationLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.notificationLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.notificationLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
