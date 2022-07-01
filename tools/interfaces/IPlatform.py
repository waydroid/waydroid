import gbinder
import logging
import time
from tools import helpers


INTERFACE = "lineageos.waydroid.IPlatform"
SERVICE_NAME = "waydroidplatform"

TRANSACTION_getprop = 1
TRANSACTION_setprop = 2
TRANSACTION_getAppsInfo = 3
TRANSACTION_getAppInfo = 4
TRANSACTION_installApp = 5
TRANSACTION_removeApp = 6
TRANSACTION_launchApp = 7
TRANSACTION_getAppName = 8
TRANSACTION_settingsPutString = 9
TRANSACTION_settingsGetString = 10
TRANSACTION_settingsPutInt = 11
TRANSACTION_settingsGetInt = 12
TRANSACTION_launchIntent = 13

class IPlatform:
    def __init__(self, remote):
        self.client = gbinder.Client(remote, INTERFACE)

    def getprop(self, arg1, arg2):
        request = self.client.new_request()
        request.append_string16(arg1)
        request.append_string16(arg2)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_getprop, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                rep1 = reader.read_string16()
                return rep1
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

    def setprop(self, arg1, arg2):
        request = self.client.new_request()
        request.append_string16(arg1)
        request.append_string16(arg2)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_setprop, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                return
            else:
                logging.error("Failed with code: {}".format(exception))

        return

    def getAppsInfo(self):
        request = self.client.new_request()
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_getAppsInfo, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            apps_list = []
            status, exception = reader.read_int32()
            if exception == 0:
                status, apps = reader.read_int32()
                for j in range(apps):
                    status, has_value = reader.read_int32()
                    if has_value == 1:
                        appinfo = {
                            "name": reader.read_string16(),
                            "packageName": reader.read_string16(),
                            "action": reader.read_string16(),
                            "launchIntent": reader.read_string16(),
                            "componentPackageName": reader.read_string16(),
                            "componentClassName": reader.read_string16(),
                            "categories": []
                        }
                        status, categories = reader.read_int32()
                        for i in range(categories):
                            appinfo["categories"].append(reader.read_string16())
                        apps_list.append(appinfo)
            else:
                logging.error("Failed with code: {}".format(exception))

        return apps_list

    def getAppInfo(self, arg1):
        request = self.client.new_request()
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_getAppInfo, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                status, has_value = reader.read_int32()
                if has_value == 1:
                    appinfo = {
                        "name": reader.read_string16(),
                        "packageName": reader.read_string16(),
                        "action": reader.read_string16(),
                        "launchIntent": reader.read_string16(),
                        "componentPackageName": reader.read_string16(),
                        "componentClassName": reader.read_string16(),
                        "categories": []
                    }
                    status, categories = reader.read_int32()
                    for i in range(categories):
                        appinfo["categories"].append(reader.read_string16())

                    return appinfo
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

    def installApp(self, arg1):
        request = self.client.new_request()
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_installApp, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                status, ret = reader.read_int32()
                return ret
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

    def removeApp(self, arg1):
        request = self.client.new_request()
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_removeApp, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                status, ret = reader.read_int32()
                return ret
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

    def launchApp(self, arg1):
        request = self.client.new_request()
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_launchApp, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception != 0:
                logging.error("Failed with code: {}".format(exception))

    def launchIntent(self, arg1, arg2):
        request = self.client.new_request()
        request.append_string16(arg1)
        request.append_string16(arg2)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_launchIntent, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                rep1 = reader.read_string16()
                return rep1
            else:
                logging.error("Failed with code: {}".format(exception))
        return None

    def getAppName(self, arg1):
        request = self.client.new_request()
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_getAppName, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                rep1 = reader.read_string16()
                return rep1
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

    def settingsPutString(self, arg1, arg2, arg3):
        request = self.client.new_request()
        request.append_int32(arg1)
        request.append_string16(arg2)
        request.append_string16(arg3)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_settingsPutString, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception != 0:
                logging.error("Failed with code: {}".format(exception))

    def settingsGetString(self, arg1, arg2):
        request = self.client.new_request()
        request.append_int32(arg1)
        request.append_string16(arg2)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_settingsGetString, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                rep1 = reader.read_string16()
                return rep1
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

    def settingsPutInt(self, arg1, arg2, arg3):
        request = self.client.new_request()
        request.append_int32(arg1)
        request.append_string16(arg2)
        request.append_int32(arg3)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_settingsPutInt, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception != 0:
                logging.error("Failed with code: {}".format(exception))

    def settingsGetInt(self, arg1, arg2):
        request = self.client.new_request()
        request.append_int32(arg1)
        request.append_string16(arg2)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_settingsGetString, request)

        if status:
            logging.error("Sending reply failed")
        else:
            reader = reply.init_reader()
            status, exception = reader.read_int32()
            if exception == 0:
                status, rep1 = reader.read_int32()
                return rep1
            else:
                logging.error("Failed with code: {}".format(exception))

        return None

def get_service(args):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
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

    return IPlatform(remote)
