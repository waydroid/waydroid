import logging
from tools.interfaces.gnss.IGnssConfiguration import IGnssConfiguration


class GnssConfiguration(IGnssConfiguration):

    def __init__(self):
        super().__init__()
        self.supl_version = 0
        self.supl_mode = 0
        self.lpp_profile = 0
        self.glonass_protocol = 0
        self.emergency_supl_pdn = False
        self.es_extension_sec = 0
        self.blocklist = []

    def set_supl_version(self, version):
        """Handle setSuplVersion request."""
        self.supl_version = version
        logging.debug(f"GnssConfiguration: SUPL version set to {version}")
        return True

    def set_supl_mode(self, mode):
        """Handle setSuplMode request."""
        self.supl_mode = mode
        logging.debug(f"GnssConfiguration: SUPL mode set to {mode}")
        return True

    def set_lpp_profile(self, profile):
        """Handle setLppProfile request."""
        self.lpp_profile = profile
        logging.debug(f"GnssConfiguration: LPP profile set to {profile}")
        return True

    def set_glonass_positioning_protocol(self, protocol):
        """Handle setGlonassPositioningProtocol request."""
        self.glonass_protocol = protocol
        logging.debug(f"GnssConfiguration: GLONASS protocol set to {protocol}")
        return True

    def set_emergency_supl_pdn(self, enable):
        """Handle setEmergencySuplPdn request."""
        self.emergency_supl_pdn = enable
        logging.debug(f"GnssConfiguration: Emergency SUPL PDN set to {enable}")
        return True

    def set_es_extension_sec(self, seconds):
        """Handle setEsExtensionSec request."""
        self.es_extension_sec = seconds
        logging.debug(f"GnssConfiguration: ES extension set to {seconds}s")
        return True

    def set_blocklist(self, blocklist):
        """Handle setBlocklist request."""
        self.blocklist = blocklist
        logging.debug(f"GnssConfiguration: Blocklist set (size={len(blocklist)})")
        return True
