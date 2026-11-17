# Copyright 2024
# SPDX-License-Identifier: GPL-3.0-or-later
"""
GNSS AIDL Data Structures.

Implements serialization for Parcelable objects defined in android.hardware.gnss definitions.

AIDL parcelable serialization format:
1. Non-null marker (int32 = 1)
2. Size placeholder (int32, will be patched after)
3. Parcelable fields
4. Patch size with actual bytes written
"""

import logging


class GnssConstellationType:
    """android.hardware.gnss.GnssConstellationType"""
    UNKNOWN = 0
    GPS = 1
    SBAS = 2
    GLONASS = 3
    QZSS = 4
    BEIDOU = 5
    GALILEO = 6
    IRNSS = 7


class GnssSvFlags:
    """IGnssCallback.GnssSvFlags"""
    NONE = 0
    HAS_EPHEMERIS_DATA = 1
    HAS_ALMANAC_DATA = 2
    USED_IN_FIX = 4
    HAS_CARRIER_FREQUENCY = 8


class GnssSvInfo:
    """
    IGnssCallback.GnssSvInfo

    Satellite vehicle info for gnssSvStatusCb callback.
    """
    def __init__(self):
        self.svid = 0
        self.constellation = GnssConstellationType.UNKNOWN
        self.cN0Dbhz = 0.0
        self.basebandCN0DbHz = 0.0
        self.elevationDegrees = 0.0
        self.azimuthDegrees = 0.0
        self.carrierFrequencyHz = 0
        self.svFlag = GnssSvFlags.NONE

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(self.svid)
        writer.append_int32(self.constellation)
        writer.append_float(self.cN0Dbhz)
        writer.append_float(self.basebandCN0DbHz)
        writer.append_float(self.elevationDegrees)
        writer.append_float(self.azimuthDegrees)
        writer.append_int64(self.carrierFrequencyHz)
        writer.append_int32(self.svFlag)

        # Patch size
        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssSignalType:
    """
    android.hardware.gnss.GnssSignalType
    """
    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(self.constellation)
        writer.append_double(self.carrierFrequencyHz)
        writer.append_string16(self.codeType)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssClock:
    """
    android.hardware.gnss.GnssClock
    """
    # Flags
    HAS_LEAP_SECOND = 1 << 0
    HAS_TIME_UNCERTAINTY = 1 << 1
    HAS_FULL_BIAS = 1 << 2
    HAS_BIAS = 1 << 3
    HAS_BIAS_UNCERTAINTY = 1 << 4
    HAS_DRIFT = 1 << 5
    HAS_DRIFT_UNCERTAINTY = 1 << 6

    def __init__(self):
        self.gnssClockFlags = 0
        self.leapSecond = 0
        self.timeNs = 0
        self.timeUncertaintyNs = 0.0
        self.fullBiasNs = 0
        self.biasNs = 0.0
        self.biasUncertaintyNs = 0.0
        self.driftNsps = 0.0
        self.driftUncertaintyNsps = 0.0
        self.hwClockDiscontinuityCount = 0
        self.referenceSignalTypeForIsb = GnssSignalType()

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(self.gnssClockFlags)
        writer.append_int32(self.leapSecond)
        writer.append_int64(self.timeNs)
        writer.append_double(self.timeUncertaintyNs)
        writer.append_int64(self.fullBiasNs)
        writer.append_double(self.biasNs)
        writer.append_double(self.biasUncertaintyNs)
        writer.append_double(self.driftNsps)
        writer.append_double(self.driftUncertaintyNsps)
        writer.append_int32(self.hwClockDiscontinuityCount)
        self.referenceSignalTypeForIsb.write_to_parcel(writer)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class ElapsedRealtime:
    """
    android.hardware.gnss.ElapsedRealtime
    """
    HAS_TIMESTAMP_NS = 1 << 0
    HAS_TIME_UNCERTAINTY_NS = 1 << 1

    def __init__(self):
        self.flags = 0
        self.timestampNs = 0
        self.timeUncertaintyNs = 0.0

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int64(self.timestampNs)
        writer.append_double(self.timeUncertaintyNs)
        writer.append_int32(self.flags)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssLocation:
    """
    android.hardware.gnss.GnssLocation

    AIDL parcelable structure for location callbacks.
    """
    HAS_LAT_LONG = 0x0001
    HAS_ALTITUDE = 0x0002
    HAS_SPEED = 0x0004
    HAS_BEARING = 0x0008
    HAS_HORIZONTAL_ACCURACY = 0x0010
    HAS_VERTICAL_ACCURACY = 0x0020
    HAS_SPEED_ACCURACY = 0x0040
    HAS_BEARING_ACCURACY = 0x0080

    def __init__(self):
        self.gnssLocationFlags = 0
        self.latitudeDegrees = 0.0
        self.longitudeDegrees = 0.0
        self.altitudeMeters = 0.0
        self.speedMetersPerSec = 0.0
        self.bearingDegrees = 0.0
        self.horizontalAccuracyMeters = 0.0
        self.verticalAccuracyMeters = 0.0
        self.speedAccuracyMetersPerSecond = 0.0
        self.bearingAccuracyDegrees = 0.0
        self.timestampMillis = 0
        self.elapsedRealtime = ElapsedRealtime()

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(self.gnssLocationFlags)
        writer.append_double(self.latitudeDegrees)
        writer.append_double(self.longitudeDegrees)
        writer.append_double(self.altitudeMeters)
        writer.append_double(self.speedMetersPerSec)
        writer.append_double(self.bearingDegrees)
        writer.append_double(self.horizontalAccuracyMeters)
        writer.append_double(self.verticalAccuracyMeters)
        writer.append_double(self.speedAccuracyMetersPerSecond)
        writer.append_double(self.bearingAccuracyDegrees)
        writer.append_int64(self.timestampMillis)
        self.elapsedRealtime.write_to_parcel(writer)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssMultipathIndicator:
    UNKNOWN = 0
    PRESENT = 1
    NOT_PRESENT = 2

class SatellitePvt:
    """
    android.hardware.gnss.SatellitePvt
    """
    HAS_POSITION_VELOCITY_CLOCK_INFO = 1 << 0
    HAS_IONO = 1 << 1
    HAS_TROPO = 1 << 2

    def __init__(self):
        self.flags = 0
        self.satPosEcef = [0.0, 0.0, 0.0] # 3 doubles
        self.satVelEcef = [0.0, 0.0, 0.0] # 3 doubles
        self.satClockInfo = [0.0, 0.0, 0.0] # 3 doubles (bias, drift, driftRate)
        self.ionoDelayMeters = 0.0
        self.tropoDelayMeters = 0.0

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(self.flags)
        # Position
        for val in self.satPosEcef:
            writer.append_double(val)
        # Velocity
        for val in self.satVelEcef:
            writer.append_double(val)
        # Clock Info
        for val in self.satClockInfo:
            writer.append_double(val)
        writer.append_double(self.ionoDelayMeters)
        writer.append_double(self.tropoDelayMeters)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class CorrelationVector:
    """
    android.hardware.gnss.CorrelationVector
    """
    def __init__(self):
        self.frequencyOffsetMps = 0.0
        self.samplingWidthM = 0.0
        self.samplingStartM = 0.0
        self.magnitude = [] # int[]

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_double(self.frequencyOffsetMps)
        writer.append_double(self.samplingWidthM)
        writer.append_double(self.samplingStartM)
        # int[] magnitude
        writer.append_int32(len(self.magnitude))
        for val in self.magnitude:
            writer.append_int32(val)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssMeasurement:
    """
    android.hardware.gnss.GnssMeasurement
    """
    def __init__(self):
        self.flags = 0
        self.svid = 0
        self.signalType = GnssSignalType()
        self.timeOffsetNs = 0.0
        self.state = 0
        self.receivedSvTimeInNs = 0
        self.receivedSvTimeUncertaintyInNs = 0
        self.antennaCN0DbHz = 0.0
        self.basebandCN0DbHz = 0.0
        self.pseudorangeRateMps = 0.0
        self.pseudorangeRateUncertaintyMps = 0.0
        self.accumulatedDeltaRangeState = 0
        self.accumulatedDeltaRangeM = 0.0
        self.accumulatedDeltaRangeUncertaintyM = 0.0
        self.carrierCycles = 0
        self.carrierPhase = 0.0
        self.carrierPhaseUncertainty = 0.0
        self.multipathIndicator = GnssMultipathIndicator.UNKNOWN
        self.snrDb = 0.0
        self.agcLevelDb = 0.0
        self.fullInterSignalBiasNs = 0.0
        self.fullInterSignalBiasUncertaintyNs = 0.0
        self.satelliteInterSignalBiasNs = 0.0
        self.satelliteInterSignalBiasUncertaintyNs = 0.0
        self.satellitePvt = SatellitePvt()
        self.correlationVectors = [] # List[CorrelationVector]

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(self.flags)
        writer.append_int32(self.svid)
        self.signalType.write_to_parcel(writer)
        writer.append_double(self.timeOffsetNs)
        writer.append_int32(self.state)
        writer.append_int64(self.receivedSvTimeInNs)
        writer.append_int64(self.receivedSvTimeUncertaintyInNs)
        writer.append_double(self.antennaCN0DbHz)
        writer.append_double(self.basebandCN0DbHz)
        writer.append_double(self.pseudorangeRateMps)
        writer.append_double(self.pseudorangeRateUncertaintyMps)
        writer.append_int32(self.accumulatedDeltaRangeState)
        writer.append_double(self.accumulatedDeltaRangeM)
        writer.append_double(self.accumulatedDeltaRangeUncertaintyM)
        writer.append_int64(self.carrierCycles)
        writer.append_double(self.carrierPhase)
        writer.append_double(self.carrierPhaseUncertainty)
        writer.append_int32(self.multipathIndicator)
        writer.append_double(self.snrDb)
        writer.append_double(self.agcLevelDb)
        writer.append_double(self.fullInterSignalBiasNs)
        writer.append_double(self.fullInterSignalBiasUncertaintyNs)
        writer.append_double(self.satelliteInterSignalBiasNs)
        writer.append_double(self.satelliteInterSignalBiasUncertaintyNs)
        self.satellitePvt.write_to_parcel(writer)
        writer.append_int32(len(self.correlationVectors))
        for cv in self.correlationVectors:
            cv.write_to_parcel(writer)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssAgc:
    """
    android.hardware.gnss.GnssData.GnssAgc
    """
    def __init__(self):
        self.agcLevelDb = 0.0
        self.constellation = 0 # GnssConstellationType
        self.carrierFrequencyHz = 0

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_double(self.agcLevelDb)
        writer.append_int32(self.constellation)
        writer.append_int64(self.carrierFrequencyHz)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)


class GnssData:
    """
    android.hardware.gnss.GnssData
    """
    def __init__(self):
        self.measurements = [] # List[GnssMeasurement]
        self.clock = GnssClock()
        self.elapsedRealtime = ElapsedRealtime()
        self.gnssAgcs = [] # List[GnssAgc]

    def write_to_parcel(self, writer):
        """Write as AIDL parcelable: non-null marker + size + fields."""
        writer.append_int32(1)  # Non-null marker
        size_pos = writer.bytes_written()
        writer.append_int32(0)  # Placeholder for size

        writer.append_int32(len(self.measurements))
        for m in self.measurements:
            m.write_to_parcel(writer)
        self.clock.write_to_parcel(writer)
        self.elapsedRealtime.write_to_parcel(writer)
        writer.append_int32(len(self.gnssAgcs))
        for agc in self.gnssAgcs:
            agc.write_to_parcel(writer)

        size = writer.bytes_written() - size_pos
        writer.overwrite_int32(size_pos, size)
