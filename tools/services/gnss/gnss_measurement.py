import logging
import time
from tools.interfaces.gnss.IGnssMeasurementInterface import IGnssMeasurementInterface
from tools.interfaces.gnss.structs import GnssData, GnssClock, ElapsedRealtime


class GnssMeasurementInterface(IGnssMeasurementInterface):

    def __init__(self):
        super().__init__()
        self.callback = None

    def on_callback_set(self, full_tracking, corr_vec_outputs):
        """Hook called when callback is set."""
        logging.debug("GnssMeasurementInterface: Callback set "
                      f"(full_tracking={full_tracking}, "
                      f"corr_vec_outputs={corr_vec_outputs})")
        # FIXME: need a way to get the necessary data from the provider

    def on_close(self):
        """Hook called when interface is closed."""
        logging.debug("GnssMeasurementInterface: Closed")
