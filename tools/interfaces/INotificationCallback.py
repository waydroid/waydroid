import gbinder
import logging
from tools import helpers
from gi.repository import GLib

INTERFACE = "lineageos.waydroid.INotifications.INotificationCallback"

TRANSACTION_onActionInvoked = 1

GBINDER_TX_FLAG_ONEWAY = 1

class INotificationCallback:
    def __init__(self, remote):
        self.remote = remote
        self.client = gbinder.Client(remote, INTERFACE)

    def addDeathHandler(self, handler):
        def local_handler(*args):
            handler(self)
        self.remote.add_death_handler(local_handler)

    def onActionInvoked(self, notification_id, action_id, xdg_activation_token):
        request = self.client.new_request()
        request.append_int32(notification_id)
        request.append_string16(action_id)
        request.append_string16(xdg_activation_token)
        self.client.transact(TRANSACTION_onActionInvoked, GBINDER_TX_FLAG_ONEWAY, request, lambda *args: None, lambda *args: None)
