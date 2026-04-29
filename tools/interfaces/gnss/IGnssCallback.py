"""
IGnssCallback interface constants and helpers.

Contains transaction codes, capability flags, and helper methods
for interacting with android.hardware.gnss.IGnssCallback.
"""

import gbinder
import logging

# Interface constants
CALLBACK_INTERFACE = "android.hardware.gnss.IGnssCallback"

# AIDL uses FIRST_CALL_TRANSACTION = 1
FIRST_CALL_TRANSACTION = 1

# IGnssCallback V2 transaction codes
CALLBACK_gnssSetCapabilitiesCb = FIRST_CALL_TRANSACTION + 0  # 1
CALLBACK_gnssStatusCb = FIRST_CALL_TRANSACTION + 1           # 2
CALLBACK_gnssSvStatusCb = FIRST_CALL_TRANSACTION + 2         # 3
CALLBACK_gnssLocationCb = FIRST_CALL_TRANSACTION + 3         # 4
CALLBACK_gnssNmeaCb = FIRST_CALL_TRANSACTION + 4             # 5

# Capability flags from IGnssCallback.h
CAPABILITY_SCHEDULING = 1 << 0
CAPABILITY_MSB = 1 << 1
CAPABILITY_MSA = 1 << 2
CAPABILITY_SINGLE_SHOT = 1 << 3
CAPABILITY_ON_DEMAND_TIME = 1 << 4
CAPABILITY_GEOFENCING = 1 << 5
CAPABILITY_MEASUREMENTS = 1 << 6
CAPABILITY_NAV_MESSAGES = 1 << 7
CAPABILITY_LOW_POWER_MODE = 1 << 8
CAPABILITY_SATELLITE_BLOCKLIST = 1 << 9
CAPABILITY_MEASUREMENT_CORRECTIONS = 1 << 10
CAPABILITY_ANTENNA_INFO = 1 << 11
CAPABILITY_CORRELATION_VECTOR = 1 << 12
CAPABILITY_SATELLITE_PVT = 1 << 13


class IGnssCallbackClient:
    """
    Client for interacting with IGnssCallback.

    Provides methods to send callbacks to the Android framework.
    """

    def __init__(self, callback_binder):
        """
        Initialize callback helper.

        Args:
            callback_binder: The binder object received from setCallback()
        """
        self.callback_binder = callback_binder
        self.callback_client = None

        if callback_binder:
            self.callback_client = gbinder.Client(
                callback_binder,
                CALLBACK_INTERFACE
            )

    def is_valid(self):
        """Check if callback is valid and ready to use."""
        return self.callback_client is not None

    def report_capabilities(self, capabilities):
        """
        Report HAL capabilities to the Android framework.

        Args:
            capabilities: Bitmask of CAPABILITY_* flags

        Returns:
            True if successful, False otherwise
        """
        if not self.callback_client:
            logging.warning("IGnssCallback: Cannot report capabilities, no callback")
            return False

        try:
            request = self.callback_client.new_request()
            request.append_int32(capabilities)

            self.callback_client.transact_sync_reply(
                CALLBACK_gnssSetCapabilitiesCb,
                request
            )
            logging.debug(f"IGnssCallback: Reported capabilities: {capabilities:#x}")
            return True
        except Exception as e:
            logging.error(f"IGnssCallback: Failed to report capabilities: {e}")
            return False

    def send_location(self, gnss_location):
        """
        Send location to Android via gnssLocationCb callback.

        Args:
            gnss_location: GnssLocation object (from tools.interfaces.gnss.structs)

        Returns:
            True if successful, False otherwise
        """
        if not self.callback_client:
            logging.warning("IGnssCallback: Cannot send location, no callback")
            return False

        try:
            request = self.callback_client.new_request()
            writer = request.init_writer()
            gnss_location.write_to_parcel(writer)

            self.callback_client.transact_sync_reply(
                CALLBACK_gnssLocationCb,
                request
            )
            return True
        except Exception as e:
            logging.error(f"IGnssCallback: Failed to send location: {e}")
            return False

    def send_sv_status(self, sv_info_list):
        """
        Send satellite visibility info via gnssSvStatusCb callback.

        Args:
            sv_info_list: List of GnssSvInfo objects

        Returns:
            True if successful, False otherwise
        """
        if not self.callback_client:
            logging.warning("IGnssCallback: Cannot send SV status, no callback")
            return False

        try:
            request = self.callback_client.new_request()

            # Write array length
            request.append_int32(len(sv_info_list))

            # Write each GnssSvInfo (write_to_parcel includes header)
            writer = request.init_writer()
            for sv_info in sv_info_list:
                sv_info.write_to_parcel(writer)

            self.callback_client.transact_sync_reply(
                CALLBACK_gnssSvStatusCb,
                request
            )
            return True
        except Exception as e:
            logging.error(f"IGnssCallback: Failed to send SV status: {e}")
            return False

    def send_nmea(self, timestamp, nmea):
        """
        Send NMEA sentence via gnssNmeaCb callback.

        Args:
            timestamp: Timestamp in milliseconds
            nmea: NMEA sentence string

        Returns:
            True if successful, False otherwise
        """
        if not self.callback_client:
            logging.warning("IGnssCallback: Cannot send NMEA, no callback")
            return False

        try:
            request = self.callback_client.new_request()
            request.append_int64(timestamp)
            request.append_string16(nmea)

            self.callback_client.transact_sync_reply(
                CALLBACK_gnssNmeaCb,
                request
            )
            return True
        except Exception as e:
            logging.error(f"IGnssCallback: Failed to send NMEA: {e}")
            return False
