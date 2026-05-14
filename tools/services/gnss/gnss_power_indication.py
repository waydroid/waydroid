import logging
from tools.interfaces.gnss.IGnssPowerIndication import IGnssPowerIndication


class GnssPowerIndication(IGnssPowerIndication):

    def __init__(self):
        super().__init__()

    def on_callback_set(self):
        """Hook called when callback is set."""
        logging.debug("GnssPowerIndication: Callback set")
        self._report_capabilities()

    def request_power_stats(self):
        """Hook called when power stats are requested."""
        logging.debug("GnssPowerIndication: Power stats requested (not implemented)")
