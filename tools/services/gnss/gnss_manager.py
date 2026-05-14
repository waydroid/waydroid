"""
GNSS HAL service for waydroid.

Provides android.hardware.gnss AIDL HAL to Android by:
1. Extending IGnss with provider integration (Gnss class)
2. Managing service lifecycle (start/stop functions)
"""

import gbinder
import logging
import threading
from gi.repository import GLib
from tools import helpers
from tools.interfaces.gnss import IGnss
from tools.interfaces.gnss.IGnssCallback import (
    CAPABILITY_SCHEDULING,
    CAPABILITY_SINGLE_SHOT,
    CAPABILITY_ON_DEMAND_TIME,
    CAPABILITY_MEASUREMENTS,
)
import tools.config
from tools.services.gnss.providers import DummyLocationProvider, LomiriLocationProvider


class Gnss(IGnss):
    """
    GNSS HAL implementation for IGnss interface.

    Extends IGnss (binder interface) with provider integration.
    """

    def __init__(self, provider=None):
        super().__init__()
        self.provider = provider
        self._location_started = False
        self._nmea_started = False

    def _create_extension_interfaces(self):
        """Create extension interface objects (service implementations)."""
        from tools.services.gnss.gnss_configuration import GnssConfiguration
        from tools.services.gnss.gnss_measurement import GnssMeasurementInterface
        from tools.services.gnss.gnss_power_indication import GnssPowerIndication
        from tools.services.gnss.gnss_psds import GnssPsds

        # Create service implementations
        self.gnss_configuration = GnssConfiguration()
        self.gnss_measurement = GnssMeasurementInterface()
        self.gnss_power_indication = GnssPowerIndication()
        self.gnss_psds = GnssPsds()

        # Create binder objects from these implementations
        self.gnss_configuration_local = self.gnss_configuration.create_local_object(self.service_manager)
        self.gnss_measurement_local = self.gnss_measurement.create_local_object(self.service_manager)
        self.gnss_power_indication_local = self.gnss_power_indication.create_local_object(self.service_manager)
        self.gnss_psds_local = self.gnss_psds.create_local_object(self.service_manager)

        logging.debug("Gnss: Created extension services")

    def get_capabilities(self):
        """Override to report capabilities based on provider."""
        caps = CAPABILITY_SCHEDULING | CAPABILITY_SINGLE_SHOT | CAPABILITY_ON_DEMAND_TIME
        if self.provider:
            caps |= CAPABILITY_MEASUREMENTS
        return caps

    def on_callback_set(self):
        """Called when Android sets the callback."""
        logging.debug("Gnss: Callback set")
        self._report_capabilities()

    def on_start(self):
        """Called when Android requests GNSS start."""
        logging.debug("Gnss: start requested")
        if self.provider and not self._location_started:
            self._start_provider()

    def on_stop(self):
        """Called when Android requests GNSS stop."""
        logging.debug("Gnss: stop requested")
        if self.provider and self._location_started:
            self.provider.stop()
            self._location_started = False

    def _start_provider(self):
        """Start the location provider."""
        if not self.provider:
            return

        def on_location(location):
            # Send location via IGnssCallback.gnssLocationCb
            self._send_location(location)

        def on_satellites(sv_list):
            # Send satellite visibility via gnssSvStatusCb
            self._send_satellites(sv_list)

        def on_nmea(timestamp, nmea):
            # TODO: NMEA can be forwarded to gnssNmeaCb
            pass

        success = self.provider.start(on_location, on_nmea, on_satellites)
        if success:
            self._location_started = True
            logging.debug("Gnss: Provider started")
        else:
            logging.warning("Gnss: Failed to start provider")

    def _send_satellites(self, sv_list):
        """Convert provider satellite list to GnssSvInfo[] and send via callback."""
        from tools.interfaces.gnss.structs import GnssSvInfo, GnssConstellationType, GnssSvFlags

        constellation_map = {
            'unknown': GnssConstellationType.UNKNOWN,
            'gps': GnssConstellationType.GPS,
            'glonass': GnssConstellationType.GLONASS,
            'galileo': GnssConstellationType.GALILEO,
            'beidou': GnssConstellationType.BEIDOU,
            'qzss': GnssConstellationType.QZSS,
            'irnss': GnssConstellationType.IRNSS,
            'sbas': GnssConstellationType.SBAS,
        }

        gnss_sv_list = []

        for sv in sv_list:
            info = GnssSvInfo()
            info.svid = sv.get('svid', 0)
            info.constellation = constellation_map.get(sv.get('constellation', 'unknown'), GnssConstellationType.UNKNOWN)
            info.cN0Dbhz = sv.get('snr', 0.0)
            info.basebandCN0DbHz = info.cN0Dbhz
            info.azimuthDegrees = sv.get('azimuth', 0.0)
            info.elevationDegrees = sv.get('elevation', 0.0)

            # Set flags
            flags = GnssSvFlags.NONE
            if sv.get('has_ephemeris', False):
                flags |= GnssSvFlags.HAS_EPHEMERIS_DATA
            if sv.get('has_almanac', False):
                flags |= GnssSvFlags.HAS_ALMANAC_DATA
            if sv.get('used_in_fix', False):
                flags |= GnssSvFlags.USED_IN_FIX
            info.svFlag = flags

            gnss_sv_list.append(info)

        if gnss_sv_list:
            self.send_sv_status(gnss_sv_list)

    def _send_location(self, location):
        """Convert provider location dict to GnssLocation and send via callback."""
        import time
        from tools.interfaces.gnss.structs import GnssLocation, ElapsedRealtime

        gnss_loc = GnssLocation()

        # Set flags based on available data
        flags = 0

        lat = location.get('latitude')
        lon = location.get('longitude')
        if lat is not None and lon is not None:
            gnss_loc.latitudeDegrees = float(lat)
            gnss_loc.longitudeDegrees = float(lon)
            flags |= GnssLocation.HAS_LAT_LONG

        alt = location.get('altitude')
        if alt is not None:
            gnss_loc.altitudeMeters = float(alt)
            flags |= GnssLocation.HAS_ALTITUDE

        speed = location.get('speed')
        if speed is not None:
            gnss_loc.speedMetersPerSec = float(speed)
            flags |= GnssLocation.HAS_SPEED

        bearing = location.get('bearing')
        if bearing is not None:
            gnss_loc.bearingDegrees = float(bearing)
            flags |= GnssLocation.HAS_BEARING

        accuracy = location.get('accuracy')
        if accuracy is not None:
            gnss_loc.horizontalAccuracyMeters = float(accuracy)
            flags |= GnssLocation.HAS_HORIZONTAL_ACCURACY

        gnss_loc.gnssLocationFlags = flags

        # Timestamp
        ts = location.get('timestamp', 0)
        if ts > 0:
            gnss_loc.timestampMillis = int(ts)
        else:
            gnss_loc.timestampMillis = int(time.time() * 1000)

        # ElapsedRealtime
        gnss_loc.elapsedRealtime.flags = ElapsedRealtime.HAS_TIMESTAMP_NS
        gnss_loc.elapsedRealtime.timestampNs = time.monotonic_ns()

        logging.debug(f"Gnss: Sending location: lat={gnss_loc.latitudeDegrees}, lon={gnss_loc.longitudeDegrees}, flags={gnss_loc.gnssLocationFlags:#x}")

        # Send via callback
        result = self.send_location(gnss_loc)

    def on_close(self):
        """Called when Android closes the HAL."""
        logging.debug("Gnss: Closing")
        if self.provider and self._location_started:
            self.provider.stop()
            self._location_started = False
        self._nmea_started = False


# Service lifecycle management
_stopping = False
_gnss_instance = None


def start(args):
    global _stopping, _gnss_instance

    # Set up D-Bus main loop for providers that need it (e.g., LomiriLocationProvider)
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)

    def service_thread():
        global _gnss_instance

        # Load config once
        cfg = tools.config.load(args)

        # Select provider
        provider = _create_provider(cfg)

        # Create GNSS Service
        _gnss_instance = Gnss(provider=provider)

        # Register on binder
        helpers.drivers.loadBinderNodes(args)
        binder_device = "/dev/" + args.BINDER_DRIVER

        # Get protocol settings
        sm_protocol = getattr(args, 'SERVICE_MANAGER_PROTOCOL', None)
        binder_protocol = getattr(args, 'BINDER_PROTOCOL', None)

        # Create service manager
        try:
            if sm_protocol and binder_protocol:
                service_manager = gbinder.ServiceManager(binder_device, sm_protocol, binder_protocol)
            elif sm_protocol:
                service_manager = gbinder.ServiceManager(binder_device, sm_protocol)
            else:
                service_manager = gbinder.ServiceManager(binder_device)
        except TypeError:
            service_manager = gbinder.ServiceManager(binder_device)

        def binder_presence():
            """Called when service manager presence changes."""
            if _stopping:
                return

            if service_manager.is_present():
                success = _gnss_instance.add_service(binder_device, sm_protocol)
                if success:
                    logging.debug("Gnss: Running on %s", binder_device)
                else:
                    logging.error("Gnss: Failed to register service")
                    args.gnss_loop.quit()

        # Check if already present, and register presence handler
        binder_presence()
        presence_id = service_manager.add_presence_handler(binder_presence)

        if presence_id:
            args.gnss_loop = GLib.MainLoop()
            try:
                args.gnss_loop.run()
            except KeyboardInterrupt:
                pass
            service_manager.remove_handler(presence_id)
        else:
            logging.error("Gnss: Failed to add presence handler")

    _stopping = False
    args.gnss_manager = threading.Thread(target=service_thread, daemon=True)
    args.gnss_manager.start()
    logging.debug("Gnss: Thread started")


def stop(args):
    global _stopping, _gnss_instance

    _stopping = True

    try:
        if hasattr(args, 'gnss_loop') and args.gnss_loop:
            args.gnss_loop.quit()
            logging.debug("Gnss: Stopped")
    except AttributeError:
        logging.debug("Gnss: Was not running")

    _gnss_instance = None


def _create_provider(cfg):
    provider_type = cfg["waydroid"].get("gnss_provider", "auto")

    if provider_type == "lomiri":
        provider = LomiriLocationProvider(cfg)
        logging.info("Gnss: Using Lomiri location provider")
        return provider

    if provider_type == "dummy":
        logging.info("Gnss: Using dummy location provider")
        return DummyLocationProvider(cfg)

    if provider_type == "auto":
        if LomiriLocationProvider.is_available():
            provider = LomiriLocationProvider(cfg)
            logging.info("Gnss: Using Lomiri location provider (auto)")
            return provider

    # provider_type == "none"
    return None
