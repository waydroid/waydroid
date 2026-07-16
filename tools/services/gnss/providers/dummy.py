"""
Dummy location provider for testing.

Emits a fixed location periodically for testing the GNSS HAL.
"""

import logging
import random
import time
from typing import Callable, Optional, Dict, Any
from gi.repository import GLib

from .base import LocationProvider


class DummyLocationProvider(LocationProvider):
    """
    Dummy provider that emits fixed test locations.

    Useful for testing the HAL without a real GPS source.
    """

    # Test location: Helsinki, Finland
    DEFAULT_LATITUDE = 60.1699
    DEFAULT_LONGITUDE = 24.9384
    DEFAULT_ALTITUDE = 26.0
    DEFAULT_ACCURACY = 20.0

    def __init__(self, config=None, interval_seconds: int = 2):
        """
        Initialize the dummy provider.

        Args:
            config: Waydroid config object
            interval_seconds: Interval between location updates.
        """
        super().__init__(config)
        self.interval_seconds = interval_seconds
        self.timer_id = None
        self.on_location = None
        self.on_nmea = None
        self.on_satellites = None
        self.update_count = 0
        self.satellites = []

        # Load coordinates from config
        self.latitude = self.DEFAULT_LATITUDE
        self.longitude = self.DEFAULT_LONGITUDE
        if self.config:
            try:
                self.latitude = float(self.config["waydroid"].get("gnss_latitude", self.DEFAULT_LATITUDE))
                self.longitude = float(self.config["waydroid"].get("gnss_longitude", self.DEFAULT_LONGITUDE))
            except Exception as e:
                logging.warning(f"DummyLocationProvider: Failed to load location from config: {e}")

        logging.info(f"DummyLocationProvider: Using location: {self.latitude}, {self.longitude}")

    def start(self,
              on_location: Callable[[Dict[str, Any]], None],
              on_nmea: Optional[Callable[[int, str], None]] = None,
              on_satellites: Optional[Callable[[list], None]] = None) -> bool:
        """Start emitting test location."""
        logging.debug(f"DummyLocationProvider: Starting (interval={self.interval_seconds}s)")

        self.on_location = on_location
        self.on_nmea = on_nmea
        self.on_satellites = on_satellites  # Not used in dummy provider
        self.update_count = 0

        # Start periodic timer
        self.timer_id = GLib.timeout_add_seconds(
            self.interval_seconds,
            self._emit_location
        )

        # Initialize satellites with some random state
        self._init_satellites()

        # Emit first location immediately
        self._emit_location()

        return True

    def stop(self) -> None:
        """Stop emitting locations."""
        logging.debug("DummyLocationProvider: Stopping")

        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

        self.on_location = None
        self.on_nmea = None
        self.on_satellites = None

    def _emit_location(self) -> bool:
        """Emit a test location update."""
        if not self.on_location:
            return False

        self.update_count += 1
        timestamp = GLib.get_real_time() // 1000  # microseconds to milliseconds

        # Add slight variation to make it look more real
        lat_offset = (self.update_count % 10) * 0.0001
        lon_offset = (self.update_count % 7) * 0.0001

        location = {
            'latitude': self.latitude + lat_offset,
            'longitude': self.longitude + lon_offset,
            'altitude': self.DEFAULT_ALTITUDE,
            'accuracy': self.DEFAULT_ACCURACY,
            'speed': 0.0,
            'bearing': 0.0,
            'timestamp': timestamp
        }

        logging.debug(f"DummyLocationProvider: Emitting location #{self.update_count}")

        try:
            self.on_location(location)
        except Exception as e:
            logging.error(f"DummyLocationProvider: Error in location callback: {e}")

        # Emit NMEA
        if self.on_nmea:
            self._emit_nmea(timestamp, location)

        # Emit satellites
        if self.on_satellites:
            self._emit_satellites()

        return True  # Continue timer

    def _init_satellites(self):
        """Initialize a random set of satellites."""
        self.satellites = []
        constellations = ['gps', 'glonass', 'galileo', 'beidou']

        # Pick 12-30 satellites
        count = random.randint(12, 30)
        for i in range(count):
            const = random.choice(constellations)
            # svid ranges (simplified)
            if const == 'gps': svid = random.randint(1, 32)
            elif const == 'glonass': svid = random.randint(65, 96)
            elif const == 'galileo': svid = random.randint(301, 336)
            else: svid = random.randint(201, 237) # beidou

            self.satellites.append({
                'svid': svid,
                'constellation': const,
                'snr': random.uniform(20.0, 40.0),
                'azimuth': random.uniform(0.0, 360.0),
                'elevation': random.uniform(10.0, 80.0),
                'has_almanac': True,
                'has_ephemeris': True,
                'used_in_fix': random.choice([True, True, False]) # Mostly used in fix
            })

    def _emit_satellites(self):
        """Emit updated satellite status."""
        if not self.on_satellites:
            return

        # Update satellite data slightly to make it look active
        for sv in self.satellites:
            sv['snr'] += random.uniform(-0.5, 0.5)
            sv['snr'] = max(10, min(50, sv['snr']))
            sv['azimuth'] = (sv['azimuth'] + random.uniform(-0.1, 0.1)) % 360
            sv['elevation'] += random.uniform(-0.05, 0.05)
            sv['elevation'] = max(5, min(90, sv['elevation']))

        try:
            self.on_satellites(self.satellites)
        except Exception as e:
            logging.error(f"DummyLocationProvider: Error in satellite callback: {e}")

    def _emit_nmea(self, timestamp: int, location: Dict[str, Any]) -> None:
        """Emit a test NMEA sentence."""
        # Generate a simple GGA sentence
        lat = location['latitude']
        lon = location['longitude']

        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lat_dir = 'N' if lat >= 0 else 'S'

        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        lon_dir = 'E' if lon >= 0 else 'W'

        # Simple GGA sentence (not checksum validated)
        nmea = f"$GPGGA,120000.00,{lat_deg:02d}{lat_min:07.4f},{lat_dir},{lon_deg:03d}{lon_min:07.4f},{lon_dir},1,08,1.0,{location['altitude']:.1f},M,0.0,M,,*00"

        try:
            self.on_nmea(timestamp, nmea)
        except Exception as e:
            logging.error(f"DummyLocationProvider: Error in NMEA callback: {e}")
