"""
IGnssMeasurementInterface AIDL HAL skeleton.

Implements android.hardware.gnss.IGnssMeasurementInterface V1 interface.
"""

import gbinder
import logging

INTERFACE = "android.hardware.gnss.IGnssMeasurementInterface"
CALLBACK_INTERFACE = "android.hardware.gnss.IGnssMeasurementCallback"

# Transaction codes
FIRST_CALL_TRANSACTION = 1
TRANSACTION_setCallback = FIRST_CALL_TRANSACTION + 0
TRANSACTION_close = FIRST_CALL_TRANSACTION + 1
TRANSACTION_setCallbackWithOptions = FIRST_CALL_TRANSACTION + 2

# AIDL interface meta-transactions
TRANSACTION_getInterfaceVersion = 16777215
TRANSACTION_getInterfaceHash = 16777214

# IGnssMeasurementInterface V2 interface hash
INTERFACE_HASH = "fc957f1d3d261d065ff5e5415f2d21caa79c310f"
INTERFACE_VERSION = 2


class IGnssMeasurementInterface:
    """
    GNSS Measurement interface skeleton.

    Provides raw GNSS measurements (pseudoranges, etc.) to the framework.
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
        logging.debug(f"IGnssMeasurementInterface: Transaction {code}")
        response = self.local.new_reply()

        if code == TRANSACTION_setCallback:
            return self._on_set_callback(req, response)
        elif code == TRANSACTION_close:
            return self._on_close(response)
        elif code == TRANSACTION_setCallbackWithOptions:
            return self._on_set_callback_with_options(req, response)
        elif code == TRANSACTION_getInterfaceVersion:
            response.append_int32(0)  # Status OK
            response.append_int32(INTERFACE_VERSION)
            return response, 0
        elif code == TRANSACTION_getInterfaceHash:
            response.append_int32(0)  # Status OK
            response.append_string16(INTERFACE_HASH)
            return response, 0
        else:
            logging.warning(f"IGnssMeasurementInterface: Unknown transaction {code}")
            response.append_int32(0)  # Status OK
            return response, 0

    def _on_set_callback(self, req, response):
        """
        Handle setCallback(callback, enableFullTracking, enableCorrVecOutputs).
        """
        reader = req.init_reader()

        self.callback_binder = reader.read_object()
        status, full_tracking = reader.read_int32()  # bool
        status, corr_vec = reader.read_int32()  # bool

        self.full_tracking = (full_tracking != 0)
        self.corr_vec_outputs = (corr_vec != 0)

        if self.callback_binder:
            self.callback_client = gbinder.Client(
                self.callback_binder,
                CALLBACK_INTERFACE
            )
            logging.debug(f"IGnssMeasurementInterface: setCallback (fullTracking={full_tracking != 0})")
            # Call hook for subclasses
            if hasattr(self, 'on_callback_set'):
                self.on_callback_set(full_tracking != 0, corr_vec != 0)
        else:
            logging.warning("IGnssMeasurementInterface: setCallback with null callback")

        response.append_int32(0)  # Status OK
        return response, 0

    def _on_set_callback_with_options(self, req, response):
        """
        Handle setCallbackWithOptions(callback, options).
        """
        reader = req.init_reader()

        self.callback_binder = reader.read_object()

        # Options is a parcelable: marker(4) + size(4) + fields
        status, marker = reader.read_int32()
        status, size = reader.read_int32()

        status, full_tracking = reader.read_int32()
        status, corr_vec = reader.read_int32()
        status, interval_ms = reader.read_int32()

        self.full_tracking = (full_tracking != 0)
        self.corr_vec_outputs = (corr_vec != 0)
        self.interval_ms = interval_ms

        if self.callback_binder:
            self.callback_client = gbinder.Client(
                self.callback_binder,
                CALLBACK_INTERFACE
            )
            logging.debug(f"IGnssMeasurementInterface: setCallbackWithOptions (fullTracking={self.full_tracking}, interval={interval_ms}ms)")
            # Call hook for subclasses
            if hasattr(self, 'on_callback_set'):
                self.on_callback_set(self.full_tracking, self.corr_vec_outputs)
        else:
            logging.warning("IGnssMeasurementInterface: setCallbackWithOptions with null callback")

        response.append_int32(0)  # Status OK
        return response, 0

    def _on_close(self, response):
        """Handle close()."""
        logging.debug("IGnssMeasurementInterface: close")
        self.callback_client = None
        self.callback_binder = None

        # Call hook
        if hasattr(self, 'on_close'):
            self.on_close()

        response.append_int32(0)
        return response, 0

    def send_gnss_data(self, gnss_data):
        """
        Send GnssData to the registered callback.

        Args:
            gnss_data: GnssData object (from tools.interfaces.gnss.structs)
        """
        if not self.callback_client:
            logging.warning("IGnssMeasurementInterface: Cannot send data, no callback")
            return False

        try:
            # CALLBACK_gnssMeasurementCb = 1 (FIRST_CALL_TRANSACTION + 0)
            CALLBACK_gnssMeasurementCb = 1
            req = self.callback_client.new_request()
            writer = req.init_writer()
            gnss_data.write_to_parcel(writer)

            self.callback_client.transact_sync_reply(CALLBACK_gnssMeasurementCb, req)
            return True
        except Exception as e:
            logging.error(f"IGnssMeasurementInterface: Failed to send data: {e}")
            return False
