"""
Lomiri location service D-Bus provider.

Connects to lomiri-location-service via D-Bus to get location updates.

The lomiri-location-service uses a bidirectional D-Bus pattern:
1. Client creates a session via CreateSessionForCriteria()
2. Client exports a D-Bus object that implements UpdatePosition/UpdateHeading/UpdateVelocity methods
3. Server calls these methods on the client when location changes
"""

import logging
from typing import Callable, Optional, Dict, Any

import dbus
import dbus.service

from .base import LocationProvider


class SessionCallback(dbus.service.Object):
    """
    D-Bus object that receives location updates from lomiri-location-service.

    The server calls UpdatePosition/UpdateHeading/UpdateVelocity methods on this object.

    Update<Position> D-Bus format (variable length due to Optional):
    - double latitude (radians)
    - double longitude (radians)
    - bool has_altitude, [double altitude if true]
    - bool has_h_accuracy, [double h_accuracy if true]
    - bool has_v_accuracy, [double v_accuracy if true]
    - int64 timestamp (nanoseconds since epoch)
    """

    SESSION_IFACE = "com.lomiri.location.Service.Session"

    def __init__(self, bus, path, provider):
        self._provider = provider
        # Use low-level message handling to accept variable signatures
        self._connection = bus.get_connection()
        bus.add_message_filter(self._message_filter)
        self._path = path
        self._bus = bus
        dbus.service.Object.__init__(self, bus, path)
        logging.debug(f"SessionCallback: Registered at {path}")

    def _message_filter(self, connection, message):
        """Filter D-Bus messages to handle UpdatePosition with variable signature."""
        if message.get_type() != 1:  # METHOD_CALL = 1
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        if message.get_path() != self._path:
            return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

        member = message.get_member()
        if member == "UpdatePosition":
            self._handle_update_position(message)
            return dbus.lowlevel.HANDLER_RESULT_HANDLED
        elif member == "UpdateHeading":
            self._handle_update_heading(message)
            return dbus.lowlevel.HANDLER_RESULT_HANDLED
        elif member == "UpdateVelocity":
            self._handle_update_velocity(message)
            return dbus.lowlevel.HANDLER_RESULT_HANDLED

        return dbus.lowlevel.HANDLER_RESULT_NOT_YET_HANDLED

    def _handle_update_position(self, message):
        """Handle UpdatePosition with variable D-Bus signature."""
        try:
            args = message.get_args_list()
            logging.info(f"SessionCallback: UpdatePosition raw args ({len(args)}): {args}")

            if len(args) < 2:
                logging.warning("SessionCallback: Not enough arguments for UpdatePosition")
                return

            # Parse variable-length Optional fields
            idx = 0
            lat = float(args[idx]); idx += 1
            lon = float(args[idx]); idx += 1

            # Optional altitude
            has_alt = bool(args[idx]); idx += 1
            alt = None
            if has_alt:
                alt = float(args[idx]); idx += 1

            # Optional horizontal accuracy
            has_h_acc = bool(args[idx]); idx += 1
            h_acc = None
            if has_h_acc:
                h_acc = float(args[idx]); idx += 1

            # Optional vertical accuracy
            has_v_acc = bool(args[idx]); idx += 1
            v_acc = None
            if has_v_acc:
                v_acc = float(args[idx]); idx += 1

            # Timestamp
            timestamp = int(args[idx]) if idx < len(args) else 0
            timestamp = timestamp // 1000000  # Convert nanoseconds to milliseconds

            # Coordinates are already in degrees (not radians as expected)
            location = {
                'latitude': lat,
                'longitude': lon,
                'timestamp': timestamp,
            }
            if alt is not None:
                location['altitude'] = alt
            if h_acc is not None:
                location['accuracy'] = h_acc

            logging.info(f"SessionCallback: Parsed position: lat={location['latitude']:.6f}, lon={location['longitude']:.6f}")
            self._provider._handle_position_update(location)

            # Send reply
            reply = dbus.lowlevel.MethodReturnMessage(message)
            self._bus.get_connection().send_message(reply)

        except Exception as e:
            logging.error(f"SessionCallback: Error parsing UpdatePosition: {e}")
            import traceback
            traceback.print_exc()

    def _handle_update_heading(self, message):
        """Handle UpdateHeading."""
        try:
            args = message.get_args_list()
            logging.debug(f"SessionCallback: UpdateHeading args: {args}")
            reply = dbus.lowlevel.MethodReturnMessage(message)
            self._bus.get_connection().send_message(reply)
        except Exception as e:
            logging.error(f"SessionCallback: Error in UpdateHeading: {e}")

    def _handle_update_velocity(self, message):
        """Handle UpdateVelocity."""
        try:
            args = message.get_args_list()
            logging.debug(f"SessionCallback: UpdateVelocity args: {args}")
            reply = dbus.lowlevel.MethodReturnMessage(message)
            self._bus.get_connection().send_message(reply)
        except Exception as e:
            logging.error(f"SessionCallback: Error in UpdateVelocity: {e}")


class LomiriLocationProvider(LocationProvider):
    """
    Location provider using lomiri-location-service D-Bus interface.

    Connects to com.lomiri.location.Service and subscribes to location
    and NMEA updates.
    """

    SERVICE_NAME = "com.lomiri.location.Service"
    SERVICE_PATH = "/com/lomiri/location/Service"
    SERVICE_IFACE = "com.lomiri.location.Service"

    @classmethod
    def is_available(cls) -> bool:
        """Check if lomiri-location-service is available on D-Bus."""
        try:
            bus = dbus.SystemBus()
            bus.get_object(cls.SERVICE_NAME, cls.SERVICE_PATH)
            return True
        except dbus.DBusException:
            return False

    def __init__(self, config=None):
        """Initialize the Lomiri provider."""
        super().__init__(config)
        self.bus = None
        self.proxy = None
        self.session_path = None
        self.session_proxy = None
        self.session_callback = None
        self.on_location = None
        self.on_nmea = None
        self.on_satellites = None
        self._nmea_signal = None
        self._sv_signal = None

    def start(self,
              on_location: Callable[[Dict[str, Any]], None],
              on_nmea: Optional[Callable[[int, str], None]] = None,
              on_satellites: Optional[Callable[[list], None]] = None) -> bool:
        """
        Start receiving location updates from lomiri-location-service.
        """
        logging.info("LomiriProvider: Starting")

        self.on_location = on_location
        self.on_nmea = on_nmea
        self.on_satellites = on_satellites

        try:
            self.bus = dbus.SystemBus()

            self.proxy = self.bus.get_object(
                self.SERVICE_NAME,
                self.SERVICE_PATH
            )

            # Create a session for position updates
            service_iface = dbus.Interface(self.proxy, self.SERVICE_IFACE)

            # CreateSessionForCriteria expects a Criteria struct
            self.session_path = service_iface.CreateSessionForCriteria(
                dbus.Boolean(True),    # requires.position
                dbus.Boolean(False),   # requires.altitude
                dbus.Boolean(False),   # requires.heading
                dbus.Boolean(False),   # requires.velocity
                dbus.Double(100.0),    # accuracy.horizontal (meters)
                dbus.Boolean(False),   # accuracy.vertical (empty optional)
                dbus.Boolean(False),   # accuracy.velocity (empty optional)
                dbus.Boolean(False),   # accuracy.heading (empty optional)
            )

            if self.session_path:
                logging.info(f"LomiriProvider: Created session at {self.session_path}")

                # Export our callback object at the SESSION PATH
                # The server will call UpdatePosition/UpdateHeading/UpdateVelocity
                # methods on this object
                self.session_callback = SessionCallback(self.bus, str(self.session_path), self)
                logging.info(f"LomiriProvider: Exported callback at {self.session_path}")

                self.session_proxy = self.bus.get_object(
                    self.SERVICE_NAME,
                    self.session_path
                )

                session_iface = dbus.Interface(
                    self.session_proxy,
                    "com.lomiri.location.Service.Session"
                )
                logging.info("LomiriProvider: Starting position updates...")
                session_iface.StartPositionUpdates()
                logging.info("LomiriProvider: Position updates started")
            else:
                logging.error("LomiriProvider: Failed to create session (no session path)")
                return False

            # Subscribe to satellite visibility if callback provided
            if on_satellites:
                self._subscribe_satellites()

            logging.info("LomiriProvider: Connected to lomiri-location-service")
            return True

        except dbus.DBusException as e:
            logging.error(f"LomiriProvider: D-Bus error: {e}")
            return False
        except Exception as e:
            logging.error(f"LomiriProvider: Failed to start: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _handle_position_update(self, location):
        """Handle position update from D-Bus callback."""
        logging.info(f"LomiriProvider: Position update: {location}")
        if self.on_location:
            self.on_location(location)

    def stop(self) -> None:
        """Stop receiving location updates."""
        logging.info("LomiriProvider: Stopping")

        try:
            if self.session_proxy:
                session_iface = dbus.Interface(
                    self.session_proxy,
                    "com.lomiri.location.Service.Session"
                )
                session_iface.StopPositionUpdates()
        except Exception as e:
            logging.warning(f"LomiriProvider: Error stopping session: {e}")

        # Clean up callback object
        if self.session_callback:
            try:
                self.session_callback.remove_from_connection()
            except:
                pass
            self.session_callback = None

        if self._sv_signal:
            self._sv_signal.remove()
            self._sv_signal = None

        self.session_proxy = None
        self.session_path = None
        self.proxy = None
        self.bus = None
        self.on_location = None
        self.on_satellites = None

    def _subscribe_satellites(self):
        """Subscribe to VisibleSpaceVehicles property changes via PropertiesChanged signal."""
        try:
            logging.info("LomiriProvider: Subscribing to satellite property changes")

            # Subscribe to PropertiesChanged signal
            self._sv_signal = self.proxy.connect_to_signal(
                "PropertiesChanged",
                self._on_properties_changed,
                dbus_interface="org.freedesktop.DBus.Properties"
            )

            logging.info("LomiriProvider: Subscribed to PropertiesChanged signal")

        except Exception as e:
            logging.warning(f"LomiriProvider: Failed to subscribe to satellite updates: {e}")
            import traceback
            traceback.print_exc()

    def _on_properties_changed(self, interface, changed, invalidated):
        """Handle D-Bus properties changed signal."""
        logging.debug(f"LomiriProvider: PropertiesChanged on {interface}: {list(changed.keys())}")

        if "VisibleSpaceVehicles" in changed:
            logging.info(f"LomiriProvider: VisibleSpaceVehicles changed, count: {len(changed['VisibleSpaceVehicles'])}")
            self._on_space_vehicles(changed["VisibleSpaceVehicles"])

    def _on_space_vehicles(self, svs):
        """Handle space vehicle visibility update."""
        if not self.on_satellites:
            return

        try:
            logging.info(f"LomiriProvider: Received satellite array with {len(svs)} satellites")
            sv_list = []

            # svs is a D-Bus array of structs from VisibleSpaceVehicles property
            # array[struct{uint32 type, uint32 id, double snr, bool has_almanac, bool has_ephemeris, bool used_in_fix, double azimuth, double elevation}]

            type_map = {
                0: 'unknown',
                1: 'beidou',
                2: 'galileo',
                3: 'glonass',
                4: 'gps',
                5: 'compass',
                6: 'irnss',
                7: 'qzss'
            }

            for sv_struct in svs:
                # Each sv_struct is a tuple/list from D-Bus array element
                if isinstance(sv_struct, (tuple, list)) and len(sv_struct) >= 8:
                    sv_type = int(sv_struct[0])
                    sv_id = int(sv_struct[1])
                    snr = float(sv_struct[2])
                    has_almanac = bool(sv_struct[3])
                    has_ephemeris = bool(sv_struct[4])
                    used_in_fix = bool(sv_struct[5])
                    azimuth = float(sv_struct[6])
                    elevation = float(sv_struct[7])

                    sv_info = {
                        'svid': sv_id,
                        'constellation': type_map.get(sv_type, 'unknown'),
                        'snr': snr,
                        'has_almanac': has_almanac,
                        'has_ephemeris': has_ephemeris,
                        'used_in_fix': used_in_fix,
                        'azimuth': azimuth,
                        'elevation': elevation,
                    }
                    sv_list.append(sv_info)
                else:
                    logging.debug(f"LomiriProvider: Unexpected SV struct format: {sv_struct}")

            if sv_list:
                logging.info(f"LomiriProvider: Parsed {len(sv_list)} satellites, sending to callback")
                self.on_satellites(sv_list)

        except Exception as e:
            logging.error(f"LomiriProvider: Error processing satellites: {e}")
            import traceback
            traceback.print_exc()
