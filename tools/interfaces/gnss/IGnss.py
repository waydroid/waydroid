"""
GNSS AIDL HAL V2 Skeleton Implementation

Implements android.hardware.gnss.IGnss V2 interface using libgbinder-python.
Registers on /dev/binder as android.hardware.gnss.IGnss/default.

"""

import gbinder
import logging
from gi.repository import GLib

from .IGnssCallback import IGnssCallbackClient

# Interface constants
INTERFACE = "android.hardware.gnss.IGnss"
SERVICE_NAME = "android.hardware.gnss.IGnss/default"

# AIDL uses FIRST_CALL_TRANSACTION = 1
FIRST_CALL_TRANSACTION = 1

# IGnss Transaction codes (from AIDL generated header)
TRANSACTION_setCallback = FIRST_CALL_TRANSACTION + 0  # 1
TRANSACTION_close = FIRST_CALL_TRANSACTION + 1        # 2
TRANSACTION_getExtensionPsds = FIRST_CALL_TRANSACTION + 2  # 3
TRANSACTION_getExtensionGnssConfiguration = FIRST_CALL_TRANSACTION + 3  # 4
TRANSACTION_getExtensionGnssMeasurement = FIRST_CALL_TRANSACTION + 4    # 5
TRANSACTION_getExtensionGnssPowerIndication = FIRST_CALL_TRANSACTION + 5  # 6
TRANSACTION_getExtensionGnssBatching = FIRST_CALL_TRANSACTION + 6
TRANSACTION_getExtensionGnssGeofence = FIRST_CALL_TRANSACTION + 7
TRANSACTION_getExtensionGnssNavigationMessage = FIRST_CALL_TRANSACTION + 8
TRANSACTION_getExtensionAGnss = FIRST_CALL_TRANSACTION + 9
TRANSACTION_getExtensionAGnssRil = FIRST_CALL_TRANSACTION + 10
TRANSACTION_getExtensionGnssDebug = FIRST_CALL_TRANSACTION + 11
TRANSACTION_getExtensionGnssVisibilityControl = FIRST_CALL_TRANSACTION + 12
TRANSACTION_start = FIRST_CALL_TRANSACTION + 13  # 14
TRANSACTION_stop = FIRST_CALL_TRANSACTION + 14   # 15
TRANSACTION_injectTime = FIRST_CALL_TRANSACTION + 15  # 16
TRANSACTION_injectLocation = FIRST_CALL_TRANSACTION + 16  # 17
TRANSACTION_injectBestLocation = FIRST_CALL_TRANSACTION + 17  # 18
TRANSACTION_deleteAidingData = FIRST_CALL_TRANSACTION + 18  # 19
TRANSACTION_setPositionMode = FIRST_CALL_TRANSACTION + 19  # 20
TRANSACTION_getExtensionGnssAntennaInfo = FIRST_CALL_TRANSACTION + 20  # 21
TRANSACTION_getExtensionMeasurementCorrections = FIRST_CALL_TRANSACTION + 21  # 22
TRANSACTION_startSvStatus = FIRST_CALL_TRANSACTION + 22  # 23
TRANSACTION_stopSvStatus = FIRST_CALL_TRANSACTION + 23   # 24
TRANSACTION_startNmea = FIRST_CALL_TRANSACTION + 24  # 25
TRANSACTION_stopNmea = FIRST_CALL_TRANSACTION + 25   # 26

# AIDL interface meta-transactions
TRANSACTION_getInterfaceVersion = 16777215
TRANSACTION_getInterfaceHash = 16777214

# IGnss interface hash for V2
INTERFACE_HASH = "fc957f1d3d261d065ff5e5415f2d21caa79c310f"
INTERFACE_VERSION = 2


class IGnss:
    """
    GNSS HAL V2 Skeleton.

    Implements the android.hardware.gnss.IGnss V2 interface.
    """

    def __init__(self):
        """
        Initialize the GNSS HAL interface.

        Note: Provider should be set in subclass (e.g. GnssService).
        """
        self.callback_client = None
        self.callback_binder = None
        self.local = None
        self.service_manager = None
        self.loop = None

        # Extension interfaces
        self.gnss_configuration = None
        self.gnss_measurement = None
        self.gnss_power_indication = None
        self.gnss_psds = None

        # Extension interface binder objects
        self.gnss_configuration_local = None
        self.gnss_measurement_local = None
        self.gnss_power_indication_local = None
        self.gnss_psds_local = None

    def add_service(self, binder_device, protocol="aidl3"):
        """
        Register the AIDL HAL service on the binder.

        Args:
            binder_device: Path to binder device
            protocol: Optional binder protocol version (defaults to aidl3)

        Returns:
            True if registration succeeded, False otherwise.
        """
        try:
            # ServiceManager(device, sm_protocol, binder_protocol)
            self.service_manager = gbinder.ServiceManager(
                binder_device, protocol, protocol
            )
        except TypeError:
            # Fallback for older gbinder versions
            try:
                self.service_manager = gbinder.ServiceManager(binder_device, sm_protocol)
            except TypeError:
                self.service_manager = gbinder.ServiceManager(binder_device)

        self.local = self.service_manager.new_local_object(
            INTERFACE,
            self._handle_transaction
        )

        # Set VINTF stability for HAL services (required for Android to accept)
        try:
            self.local.set_stability(gbinder.STABILITY_VINTF)
        except (AttributeError, TypeError):
            logging.warning("IGnss: Could not set VINTF stability (older gbinder?)")

        status = self.service_manager.add_service_sync(SERVICE_NAME, self.local)
        if status:
            logging.error(f"Failed to add service {SERVICE_NAME}: {status}")
            return False

        logging.debug(f"Registered service: {SERVICE_NAME}")

        # Create extension interfaces
        self._create_extension_interfaces()

        return True

    def _handle_transaction(self, req, code, flags):
        """
        Handle incoming binder transactions.

        Args:
            req: The incoming request (RemoteRequest)
            code: Transaction code
            flags: Transaction flags

        Returns:
            Tuple of (response, status_code)
        """
        logging.debug(f"IGnss: Received transaction: {code}")
        response = self.local.new_reply()

        if code == TRANSACTION_setCallback:
            return self._on_set_callback(req, response)
        elif code == TRANSACTION_close:
            return self._on_close(response)
        elif code == TRANSACTION_getExtensionPsds:
            return self._on_get_extension_psds(response)
        elif code == TRANSACTION_getExtensionGnssConfiguration:
            return self._on_get_extension_gnss_configuration(response)
        elif code == TRANSACTION_getExtensionGnssMeasurement:
            return self._on_get_extension_gnss_measurement(response)
        elif code == TRANSACTION_getExtensionGnssPowerIndication:
            return self._on_get_extension_gnss_power_indication(response)
        elif code == TRANSACTION_getExtensionGnssBatching:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionGnssGeofence:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionGnssNavigationMessage:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionAGnss:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionAGnssRil:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionGnssDebug:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionGnssVisibilityControl:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionGnssAntennaInfo:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_getExtensionMeasurementCorrections:
            return self._on_get_extension_null(response)
        elif code == TRANSACTION_start:
            return self._on_start(response)
        elif code == TRANSACTION_stop:
            return self._on_stop(response)
        elif code == TRANSACTION_injectTime:
            return self._on_inject_time(req, response)
        elif code == TRANSACTION_injectLocation:
            return self._on_inject_location(req, response)
        elif code == TRANSACTION_injectBestLocation:
            return self._on_inject_location(req, response)
        elif code == TRANSACTION_deleteAidingData:
            return self._on_delete_aiding_data(req, response)
        elif code == TRANSACTION_setPositionMode:
            return self._on_set_position_mode(req, response)
        elif code == TRANSACTION_startSvStatus:
            return self._on_start_sv_status(response)
        elif code == TRANSACTION_stopSvStatus:
            return self._on_stop_sv_status(response)
        elif code == TRANSACTION_startNmea:
            return self._on_start_nmea(response)
        elif code == TRANSACTION_stopNmea:
            return self._on_stop_nmea(response)
        elif code == TRANSACTION_getInterfaceVersion:
            return self._on_get_interface_version(response)
        elif code == TRANSACTION_getInterfaceHash:
            return self._on_get_interface_hash(response)
        else:
            logging.warning(f"IGnss: Unknown transaction code: {code}")
            response.append_int32(0)  # Status OK even for unknown
            return response, 0

    def _on_set_callback(self, req, response):
        """
        Handle setCallback(IGnssCallback callback).

        Stores the callback and calls on_callback_set() hook.
        """
        logging.debug("IGnss: setCallback")
        reader = req.init_reader()

        # Read the callback binder object
        callback_binder = reader.read_object()

        if callback_binder:
            self.callback = IGnssCallbackClient(callback_binder)
            logging.debug("IGnss: Callback registered")
            # Call hook for subclasses
            if hasattr(self, 'on_callback_set'):
                self.on_callback_set()
        else:
            logging.warning("IGnss: setCallback received null callback")
            self.callback = None
        # Return void (just status)
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_close(self, response):
        """
        Handle close().

        Clears callback and calls on_close() hook.
        """
        logging.debug("IGnss: close")
        self.callback_client = None
        self.callback_binder = None

        if hasattr(self, 'on_close'):
            self.on_close()

        response.append_int32(0)  # Status OK
        return response, 0

    def _on_get_extension_psds(self, response):
        """
        Handle getExtensionPsds() -> @nullable IGnssPsds.
        """
        logging.debug("IGnss: getExtensionPsds")
        response.append_int32(0)  # Status OK
        if self.gnss_psds_local:
            response.append_local_object(self.gnss_psds_local)
        else:
            response.append_int32(0)  # null binder
        return response, 0

    def _on_get_extension_gnss_configuration(self, response):
        """
        Handle getExtensionGnssConfiguration() -> IGnssConfiguration.
        """
        logging.debug("IGnss: getExtensionGnssConfiguration")
        response.append_int32(0)  # Status OK
        if self.gnss_configuration_local:
            response.append_local_object(self.gnss_configuration_local)
        else:
            response.append_int32(0)  # null binder
        return response, 0

    def _on_get_extension_gnss_measurement(self, response):
        """
        Handle getExtensionGnssMeasurement() -> IGnssMeasurementInterface.
        """
        logging.debug("IGnss: getExtensionGnssMeasurement")
        response.append_int32(0)  # Status OK
        if self.gnss_measurement_local:
            response.append_local_object(self.gnss_measurement_local)
        else:
            response.append_int32(0)  # null binder
        return response, 0

    def _on_get_extension_gnss_power_indication(self, response):
        """
        Handle getExtensionGnssPowerIndication() -> IGnssPowerIndication.
        """
        logging.debug("IGnss: getExtensionGnssPowerIndication")
        response.append_int32(0)  # Status OK
        if self.gnss_power_indication_local:
            response.append_local_object(self.gnss_power_indication_local)
        else:
            response.append_int32(0)  # null binder
        return response, 0

    def _on_get_extension_null(self, response):
        """Handle getExtension* calls that return null (unsupported interfaces)."""
        response.append_int32(0)  # Status OK
        response.append_int32(0)  # null binder (no remote object)
        return response, 0

    def _on_start(self, response):
        """Handle start() -> bool."""
        logging.debug("IGnss: start")
        if hasattr(self, 'on_start'):
            self.on_start()
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_stop(self, response):
        """Handle stop() -> bool."""
        logging.debug("IGnss: stop")
        if hasattr(self, 'on_stop'):
            self.on_stop()
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_inject_time(self, req, response):
        """Handle injectTime(timeMs, timeReferenceMs, uncertaintyMs)."""
        logging.debug("IGnss: injectTime")
        reader = req.init_reader()
        try:
            _, time_ms = reader.read_int64()
            _, time_ref_ms = reader.read_int64()
            _, uncertainty = reader.read_int32()
            if hasattr(self, 'on_inject_time'):
                self.on_inject_time(time_ms, time_ref_ms, uncertainty)
        except Exception as e:
            logging.warning(f"IGnss: Failed to parse injectTime: {e}")
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_inject_location(self, req, response):
        """Handle injectLocation/injectBestLocation (GnssLocation parcelable)."""
        logging.debug("IGnss: injectLocation")
        reader = req.init_reader()
        try:
            # Read parcelable marker and size
            _, marker = reader.read_int32()
            _, size = reader.read_int32()
            if marker != 0:  # Non-null parcelable
                # Read GnssLocation fields
                _, flags = reader.read_int32()
                _, lat = reader.read_double()
                _, lon = reader.read_double()
                # Skip to accuracy (alt, speed, bearing, then accuracy)
                reader.read_double()  # altitude
                reader.read_double()  # speed
                reader.read_double()  # bearing
                _, accuracy = reader.read_double()
                if hasattr(self, 'on_inject_location'):
                    self.on_inject_location(lat, lon, accuracy)
        except Exception as e:
            logging.warning(f"IGnss: Failed to parse injectLocation: {e}")
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_delete_aiding_data(self, req, response):
        """Handle deleteAidingData(flags)."""
        logging.debug("IGnss: deleteAidingData")
        reader = req.init_reader()
        try:
            _, flags = reader.read_int32()
            if hasattr(self, 'on_delete_aiding_data'):
                self.on_delete_aiding_data(flags)
        except Exception as e:
            logging.warning(f"IGnss: Failed to parse deleteAidingData: {e}")
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_set_position_mode(self, req, response):
        """Handle setPositionMode(PositionModeOptions parcelable)."""
        logging.debug("IGnss: setPositionMode")
        reader = req.init_reader()
        try:
            # Read parcelable marker and size
            _, marker = reader.read_int32()
            _, size = reader.read_int32()
            if marker != 0:  # Non-null parcelable
                _, mode = reader.read_int32()
                _, recurrence = reader.read_int32()
                _, min_interval = reader.read_int32()
                _, pref_accuracy = reader.read_int32()
                _, pref_time = reader.read_int32()
                if hasattr(self, 'on_set_position_mode'):
                    self.on_set_position_mode(mode, recurrence, min_interval, pref_accuracy, pref_time)
        except Exception as e:
            logging.warning(f"IGnss: Failed to parse setPositionMode: {e}")
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_start_sv_status(self, response):
        """Handle startSvStatus()."""
        logging.debug("IGnss: startSvStatus")
        if hasattr(self, 'on_start_sv_status'):
            self.on_start_sv_status()
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_stop_sv_status(self, response):
        """Handle stopSvStatus()."""
        logging.debug("IGnss: stopSvStatus")
        if hasattr(self, 'on_stop_sv_status'):
            self.on_stop_sv_status()
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_start_nmea(self, response):
        """Handle startNmea()."""
        logging.debug("IGnss: startNmea")
        if hasattr(self, 'on_start_nmea'):
            self.on_start_nmea()
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_stop_nmea(self, response):
        """Handle stopNmea()."""
        logging.debug("IGnss: stopNmea")
        if hasattr(self, 'on_stop_nmea'):
            self.on_stop_nmea()
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_get_interface_version(self, response):
        """Handle getInterfaceVersion() -> int."""
        logging.debug("IGnss: getInterfaceVersion")
        response.append_int32(0)  # Status OK
        response.append_int32(INTERFACE_VERSION)
        return response, 0

    def _on_get_interface_hash(self, response):
        """Handle getInterfaceHash() -> String."""
        logging.debug("IGnss: getInterfaceHash")
        response.append_int32(0)  # Status OK
        response.append_string16(INTERFACE_HASH)
        return response, 0

    def _create_extension_interfaces(self):
        """Create extension interface objects."""
        from .IGnssConfiguration import IGnssConfiguration
        from .IGnssMeasurementInterface import IGnssMeasurementInterface
        from .IGnssPowerIndication import IGnssPowerIndication
        from .IGnssPsds import IGnssPsds

        # Create interface handlers
        self.gnss_configuration = IGnssConfiguration()
        self.gnss_measurement = IGnssMeasurementInterface()
        self.gnss_power_indication = IGnssPowerIndication()
        self.gnss_psds = IGnssPsds()

        # Create binder objects
        self.gnss_configuration_local = self.gnss_configuration.create_local_object(self.service_manager)
        self.gnss_measurement_local = self.gnss_measurement.create_local_object(self.service_manager)
        self.gnss_power_indication_local = self.gnss_power_indication.create_local_object(self.service_manager)
        self.gnss_psds_local = self.gnss_psds.create_local_object(self.service_manager)

        logging.debug("IGnss: Created extension interfaces")

    def _report_capabilities(self):
        """Report HAL capabilities to the Android framework via callback."""
        if not self.callback:
            logging.warning("IGnss: Cannot report capabilities, no callback")
            return

        # Get capabilities (can be overridden by subclass)
        if hasattr(self, 'get_capabilities'):
            capabilities = self.get_capabilities()
        else:
            # Import capability flags from IGnssCallback
            from .IGnssCallback import (
                CAPABILITY_SCHEDULING,
                CAPABILITY_SINGLE_SHOT,
                CAPABILITY_ON_DEMAND_TIME
            )
            # Default capabilities if not overridden
            capabilities = (
                CAPABILITY_SCHEDULING |
                CAPABILITY_SINGLE_SHOT |
                CAPABILITY_ON_DEMAND_TIME
            )

        self.callback.report_capabilities(capabilities)

    def send_location(self, gnss_location):
        """
        Send location to Android via gnssLocationCb callback.

        Args:
            gnss_location: GnssLocation object (from tools.interfaces.gnss.structs)

        Returns:
            True if successful, False otherwise
        """
        if not self.callback:
            logging.warning("IGnss: Cannot send location, no callback")
            return False

        return self.callback.send_location(gnss_location)

    def send_sv_status(self, sv_info_list):
        """
        Send satellite visibility info via gnssSvStatusCb callback.

        Args:
            sv_info_list: List of GnssSvInfo objects

        Returns:
            True if successful, False otherwise
        """
        if not self.callback:
            logging.warning("IGnss: Cannot send SV status, no callback")
            return False

        return self.callback.send_sv_status(sv_info_list)