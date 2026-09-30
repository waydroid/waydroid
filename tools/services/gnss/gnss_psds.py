import logging
from tools.interfaces.gnss.IGnssPsds import IGnssPsds


class GnssPsds(IGnssPsds):

    def __init__(self):
        super().__init__()

    def on_inject_psds_data(self, psds_type, data):
        """Hook called when PSDS data is injected."""
        logging.debug(f"GnssPsds: Injected data type={psds_type}, size={len(data) if data else 0}")
        return True

    def on_callback_set(self):
        """Hook called when callback is set."""
        logging.debug("GnssPsds: Callback set")
