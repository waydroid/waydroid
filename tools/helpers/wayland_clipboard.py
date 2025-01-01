import logging
import subprocess
import shutil

class WaylandClipboardHandler:
    def __init__(self):
        self.wl_copy = shutil.which('wl-copy')
        self.wl_paste = shutil.which('wl-paste')
        if not self.wl_copy or not self.wl_paste:
            raise Exception("wl-clipboard must be installed. Please install wl-clipboard using your system package manager")

    def copy(self, value):
        try:
            if not isinstance(value, (str, bytes)):
                raise TypeError(f"Data must be str or bytes, not {type(value)}")

            args = [self.wl_copy]
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                text=isinstance(value, str)
            )
            stdout, stderr = proc.communicate(value)

            if proc.returncode != 0:
                raise Exception(f"Copy failed. wl-copy returned code: {proc.returncode}")
        except Exception as e:
            logging.debug(str(e))

    def paste(self):
        try:
            args = [self.wl_paste, '--no-newline']
            completed_proc = subprocess.run(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if completed_proc.returncode != 0:
                raise Exception(f"Paste failed. wl-paste returned code: {completed_proc.returncode}")

            return completed_proc.stdout
        except Exception as e:
            logging.debug(str(e))
            return ""
