"""
IGnssPsds AIDL HAL skeleton.

Implements android.hardware.gnss.IGnssPsds V1 interface.
PSDS = Predicted Satellite Data Service (formerly XTRA).
"""

import gbinder
import logging

INTERFACE = "android.hardware.gnss.IGnssPsds"
CALLBACK_INTERFACE = "android.hardware.gnss.IGnssPsdsCallback"

# Transaction codes
FIRST_CALL_TRANSACTION = 1
TRANSACTION_injectPsdsData = FIRST_CALL_TRANSACTION + 0
TRANSACTION_setCallback = FIRST_CALL_TRANSACTION + 1

# AIDL interface meta-transactions
TRANSACTION_getInterfaceVersion = 16777215
TRANSACTION_getInterfaceHash = 16777214

# Interface hash for V2
INTERFACE_HASH = "fc957f1d3d261d065ff5e5415f2d21caa79c310f"
INTERFACE_VERSION = 2

# Callback transaction codes
CALLBACK_downloadRequestCb = FIRST_CALL_TRANSACTION + 0

# PsdsType enum from PsdsType.h
PSDS_TYPE_UNKNOWN = 0
PSDS_TYPE_1 = 1
PSDS_TYPE_2 = 2
PSDS_TYPE_3 = 3
PSDS_TYPE_REALTIME = 4
PSDS_TYPE_LONG_TERM = 5


class IGnssPsds:
    """
    GNSS PSDS (Predicted Satellite Data Service) interface skeleton.

    Handles injection of assistance data for faster GPS acquisition.
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
        logging.debug(f"IGnssPsds: Transaction {code}")
        response = self.local.new_reply()

        if code == TRANSACTION_injectPsdsData:
            return self._on_inject_psds_data(req, response)
        elif code == TRANSACTION_setCallback:
            return self._on_set_callback(req, response)
        elif code == TRANSACTION_getInterfaceVersion:
            response.append_int32(0)  # Status OK
            response.append_int32(INTERFACE_VERSION)
            return response, 0
        elif code == TRANSACTION_getInterfaceHash:
            response.append_int32(0)  # Status OK
            response.append_string16(INTERFACE_HASH)
            return response, 0
        else:
            logging.warning(f"IGnssPsds: Unknown transaction {code}")
            response.append_int32(0)  # Status OK
            return response, 0

    def _on_inject_psds_data(self, req, response):
        """Handle injectPsdsData(PsdsType psdsType, byte[] psdsData)."""
        reader = req.init_reader()

        status, psds_type = reader.read_int32()
        # TODO: Read byte array properly

        logging.debug(f"IGnssPsds: injectPsdsData (type={psds_type})")

        # Read byte array from reader (Need to check gbinder-python API for byte/blob array)
        # For now assuming it's consumable

        # Call hook
        if hasattr(self, 'on_inject_psds_data'):
            self.on_inject_psds_data(psds_type, None)

        response.append_int32(0)  # Status OK
        return response, 0

    def _on_set_callback(self, req, response):
        """Handle setCallback(IGnssPsdsCallback callback)."""
        reader = req.init_reader()

        self.callback_binder = reader.read_object()

        if self.callback_binder:
            self.callback_client = gbinder.Client(
                self.callback_binder,
                CALLBACK_INTERFACE
            )
            logging.debug("IGnssPsds: setCallback")
            # Call hook
            if hasattr(self, 'on_callback_set'):
                self.on_callback_set()
        else:
            logging.warning("IGnssPsds: setCallback with null callback")

        response.append_int32(0)  # Status OK
        return response, 0

    def request_download(self, psds_type=PSDS_TYPE_1):
        """
        Request PSDS data download via callback.

        Framework should respond by calling injectPsdsData() with the data.
        """
        if not self.callback_client:
            logging.warning("IGnssPsds: Cannot request download, no callback")
            return

        try:
            request = self.callback_client.new_request()
            request.append_int32(psds_type)
            self.callback_client.transact_sync_reply(CALLBACK_downloadRequestCb, request)
            logging.debug(f"IGnssPsds: Requested download (type={psds_type})")
        except Exception as e:
            logging.error(f"IGnssPsds: Failed to request download: {e}")
