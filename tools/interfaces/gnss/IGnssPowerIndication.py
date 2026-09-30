"""
IGnssPowerIndication AIDL HAL skeleton.

Implements android.hardware.gnss.IGnssPowerIndication V1 interface.
"""

import gbinder
import logging

INTERFACE = "android.hardware.gnss.IGnssPowerIndication"
CALLBACK_INTERFACE = "android.hardware.gnss.IGnssPowerIndicationCallback"

# Transaction codes
FIRST_CALL_TRANSACTION = 1
TRANSACTION_setCallback = FIRST_CALL_TRANSACTION + 0
TRANSACTION_requestGnssPowerStats = FIRST_CALL_TRANSACTION + 1

# AIDL interface meta-transactions
TRANSACTION_getInterfaceVersion = 16777215
TRANSACTION_getInterfaceHash = 16777214

# IGnssPowerIndication V2 interface hash
INTERFACE_HASH = "fc957f1d3d261d065ff5e5415f2d21caa79c310f"
INTERFACE_VERSION = 2

# Callback transaction codes
CALLBACK_setCapabilitiesCb = FIRST_CALL_TRANSACTION + 0
CALLBACK_gnssPowerStatsCb = FIRST_CALL_TRANSACTION + 1


class IGnssPowerIndication:
    """
    GNSS Power Indication interface skeleton.

    Reports GNSS power consumption statistics to the framework.
    """

    def __init__(self):
        self.callback_client = None
        self.callback_binder = None

    def create_local_object(self, service_manager):
        """Create a local binder object for this interface."""
        self.local = service_manager.new_local_object(
            INTERFACE,
            self._handle_transaction
        )
        # Set VINTF stability for HAL services
        try:
            self.local.set_stability(gbinder.STABILITY_VINTF)
        except (AttributeError, TypeError):
            pass
        return self.local

    def _handle_transaction(self, req, code, flags):
        """Handle incoming binder transactions."""
        logging.debug(f"IGnssPowerIndication: Transaction {code}")
        response = self.local.new_reply()

        if code == TRANSACTION_setCallback:
            return self._on_set_callback(req, response)
        elif code == TRANSACTION_requestGnssPowerStats:
            return self._on_request_power_stats(response)
        elif code == TRANSACTION_getInterfaceVersion:
            response.append_int32(0)  # Status OK
            response.append_int32(INTERFACE_VERSION)
            return response, 0
        elif code == TRANSACTION_getInterfaceHash:
            response.append_int32(0)  # Status OK
            response.append_string16(INTERFACE_HASH)
            return response, 0
        else:
            logging.warning(f"IGnssPowerIndication: Unknown transaction {code}")
            response.append_int32(0)  # Status OK
            return response, 0

    def _on_set_callback(self, req, response):
        """Handle setCallback(IGnssPowerIndicationCallback callback)."""
        reader = req.init_reader()

        self.callback_binder = reader.read_object()

        if self.callback_binder:
            self.callback_client = gbinder.Client(
                self.callback_binder,
                CALLBACK_INTERFACE
            )
            logging.debug("IGnssPowerIndication: setCallback")

            # Call hook for subclasses
            if hasattr(self, 'on_callback_set'):
                self.on_callback_set()
        else:
            logging.warning("IGnssPowerIndication: setCallback with null callback")

        response.append_int32(0)  # Status OK
        return response, 0

    def _on_request_power_stats(self, response):
        """Handle requestGnssPowerStats()."""
        logging.debug("IGnssPowerIndication: requestGnssPowerStats")

        # Call hook
        if hasattr(self, 'request_power_stats'):
            self.request_power_stats()

        response.append_int32(0)  # Status OK
        return response, 0

    def _report_capabilities(self):
        """Report power indication capabilities via callback."""
        if not self.callback_client:
            return

        try:
            request = self.callback_client.new_request()
            # Capabilities = 0 (no power stats supported yet)
            request.append_int32(0)
            self.callback_client.transact_sync_reply(CALLBACK_setCapabilitiesCb, request)
        except Exception as e:
            logging.error(f"IGnssPowerIndication: Failed to report capabilities: {e}")
