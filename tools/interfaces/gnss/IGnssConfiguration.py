"""
IGnssConfiguration AIDL HAL skeleton.

Implements android.hardware.gnss.IGnssConfiguration V1 interface.
"""

import gbinder
import logging

INTERFACE = "android.hardware.gnss.IGnssConfiguration"

# Transaction codes (FIRST_CALL_TRANSACTION = 1)
FIRST_CALL_TRANSACTION = 1
TRANSACTION_setSuplVersion = FIRST_CALL_TRANSACTION + 0
TRANSACTION_setSuplMode = FIRST_CALL_TRANSACTION + 1
TRANSACTION_setLppProfile = FIRST_CALL_TRANSACTION + 2
TRANSACTION_setGlonassPositioningProtocol = FIRST_CALL_TRANSACTION + 3
TRANSACTION_setEmergencySuplPdn = FIRST_CALL_TRANSACTION + 4
TRANSACTION_setEsExtensionSec = FIRST_CALL_TRANSACTION + 5
TRANSACTION_setBlocklist = FIRST_CALL_TRANSACTION + 6

# AIDL interface meta-transactions
TRANSACTION_getInterfaceVersion = 16777215
TRANSACTION_getInterfaceHash = 16777214

# IGnssConfiguration V2 interface hash
INTERFACE_HASH = "fc957f1d3d261d065ff5e5415f2d21caa79c310f"
INTERFACE_VERSION = 2

# Constants from header
SUPL_MODE_MSB = 1
SUPL_MODE_MSA = 2
LPP_PROFILE_USER_PLANE = 1
LPP_PROFILE_CONTROL_PLANE = 2
GLONASS_POS_PROTOCOL_RRC_CPLANE = 1
GLONASS_POS_PROTOCOL_RRLP_UPLANE = 2
GLONASS_POS_PROTOCOL_LPP_UPLANE = 4


class IGnssConfiguration:
    """
    GNSS Configuration interface skeleton.

    Handles GNSS configuration settings from the Android framework.
    """

    def __init__(self):
        pass

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
        logging.debug(f"IGnssConfiguration: Transaction {code}")
        response = self.local.new_reply()

        if code == TRANSACTION_setSuplVersion:
            return self._on_set_supl_version(req, response)
        elif code == TRANSACTION_setSuplMode:
            return self._on_set_supl_mode(req, response)
        elif code == TRANSACTION_setLppProfile:
            return self._on_set_lpp_profile(req, response)
        elif code == TRANSACTION_setGlonassPositioningProtocol:
            return self._on_set_glonass_protocol(req, response)
        elif code == TRANSACTION_setEmergencySuplPdn:
            return self._on_set_emergency_supl_pdn(req, response)
        elif code == TRANSACTION_setEsExtensionSec:
            return self._on_set_es_extension_sec(req, response)
        elif code == TRANSACTION_setBlocklist:
            return self._on_set_blocklist(req, response)
        elif code == TRANSACTION_getInterfaceVersion:
            response.append_int32(0)  # Status OK
            response.append_int32(INTERFACE_VERSION)
            return response, 0
        elif code == TRANSACTION_getInterfaceHash:
            response.append_int32(0)  # Status OK
            response.append_string16(INTERFACE_HASH)
            return response, 0
        else:
            logging.warning(f"IGnssConfiguration: Unknown transaction {code}")
            response.append_int32(0)  # Status OK
            return response, 0

    def _on_set_supl_version(self, req, response):
        reader = req.init_reader()
        status, version = reader.read_int32()
        logging.debug(f"IGnssConfiguration: setSuplVersion({version})")
        if hasattr(self, 'set_supl_version'):
            self.set_supl_version(version)
        response.append_int32(0)  # Status OK
        return response, 0

    def _on_set_supl_mode(self, req, response):
        reader = req.init_reader()
        status, mode = reader.read_int32()
        logging.debug(f"IGnssConfiguration: setSuplMode({mode})")
        if hasattr(self, 'set_supl_mode'):
            self.set_supl_mode(mode)
        response.append_int32(0)
        return response, 0

    def _on_set_lpp_profile(self, req, response):
        reader = req.init_reader()
        status, profile = reader.read_int32()
        logging.debug(f"IGnssConfiguration: setLppProfile({profile})")
        if hasattr(self, 'set_lpp_profile'):
            self.set_lpp_profile(profile)
        response.append_int32(0)
        return response, 0

    def _on_set_glonass_protocol(self, req, response):
        reader = req.init_reader()
        status, protocol = reader.read_int32()
        logging.debug(f"IGnssConfiguration: setGlonassPositioningProtocol({protocol})")
        if hasattr(self, 'set_glonass_positioning_protocol'):
            self.set_glonass_positioning_protocol(protocol)
        response.append_int32(0)
        return response, 0

    def _on_set_emergency_supl_pdn(self, req, response):
        reader = req.init_reader()
        status, enable = reader.read_int32()  # bool as int
        logging.debug(f"IGnssConfiguration: setEmergencySuplPdn({enable})")
        if hasattr(self, 'set_emergency_supl_pdn'):
            self.set_emergency_supl_pdn(enable != 0)
        response.append_int32(0)
        return response, 0

    def _on_set_es_extension_sec(self, req, response):
        reader = req.init_reader()
        status, seconds = reader.read_int32()
        logging.debug(f"IGnssConfiguration: setEsExtensionSec({seconds})")
        if hasattr(self, 'set_es_extension_sec'):
            self.set_es_extension_sec(seconds)
        response.append_int32(0)
        return response, 0

    def _on_set_blocklist(self, req, response):
        # TODO: Parse BlocklistedSource parcelable array
        logging.debug("IGnssConfiguration: setBlocklist")
        if hasattr(self, 'set_blocklist'):
            self.set_blocklist([])
        response.append_int32(0)
        return response, 0
