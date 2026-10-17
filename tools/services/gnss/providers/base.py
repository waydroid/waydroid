"""
Abstract base class for location providers.

Location providers are pluggable backends that supply location data
to the GNSS HAL skeleton.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any


class LocationProvider(ABC):
    """
    Abstract base class for location providers.

    Subclasses must implement start() and stop() methods.
    """

    def __init__(self, config=None):
        self.config = config

    @abstractmethod
    def start(self,
              on_location: Callable[[Dict[str, Any]], None],
              on_nmea: Optional[Callable[[int, str], None]] = None,
              on_satellites: Optional[Callable[[list], None]] = None) -> bool:
        """
        Start providing location updates.

        Args:
            on_location: Callback for location updates. Called with dict containing:
                - latitude: float (degrees)
                - longitude: float (degrees)
                - altitude: float (meters, optional)
                - accuracy: float (meters, optional)
                - speed: float (m/s, optional)
                - bearing: float (degrees, optional)
                - timestamp: int (milliseconds since epoch)
            on_nmea: Optional callback for NMEA sentences.
                Called with (timestamp_ms, nmea_sentence).
            on_satellites: Optional callback for satellite visibility updates.
                Called with list of dicts, each containing:
                - svid: int
                - constellation: str ('gps', 'glonass', 'galileo', 'beidou', etc.)
                - snr: float
                - azimuth: float (degrees)
                - elevation: float (degrees)
                - has_almanac: bool
                - has_ephemeris: bool
                - used_in_fix: bool

        Returns:
            True if started successfully, False otherwise.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop providing location updates."""
        pass
