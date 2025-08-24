# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from logging.handlers import RotatingFileHandler
import os
import sys


class stdout_logger(logging.StreamHandler):
    """
    Write to stdout and to the already opened log file.
    """
    _args = None

    def emit(self, record):
        # INFO or higher: Write to stdout
        if self._args.quiet or (
                record.levelno < logging.INFO and
                not self._args.details_to_stdout):
            return

        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg)
            stream.write(self.terminator)
            self.flush()

        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            self.handleError(record)


def add_verbose_log_level():
    """
    Add a new log level "verbose", which is below "debug". Also monkeypatch
    logging, so it can be used with logging.verbose().

    This function is based on work by Voitek Zylinski and sleepycal:
    https://stackoverflow.com/a/20602183
    All stackoverflow user contributions are licensed as CC-BY-SA:
    https://creativecommons.org/licenses/by-sa/3.0/
    """
    logging.VERBOSE = 5
    logging.addLevelName(logging.VERBOSE, "VERBOSE")
    logging.Logger.verbose = lambda inst, msg, * \
        args, **kwargs: inst.log(logging.VERBOSE, msg, *args, **kwargs)
    logging.verbose = lambda msg, *args, **kwargs: logging.log(logging.VERBOSE,
                                                               msg, *args,
                                                               **kwargs)


def init(args):
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Set log level
    add_verbose_log_level()
    root_logger.setLevel(logging.DEBUG)
    if args.verbose:
        root_logger.setLevel(logging.VERBOSE)

    # Add custom stdout log handler
    handler = stdout_logger()
    handler._args = args
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s",
                                  datefmt="%H:%M:%S"))
    root_logger.addHandler(handler)

    # Add file log handler
    if args.action == "container" and not args.details_to_stdout:
        os.chmod(args.log, 0o644)
        handler = RotatingFileHandler(args.log, maxBytes=5*1024*1024)
        handler.setFormatter(logging.Formatter("(%(process)d) [%(asctime)s] %(message)s",
                                      datefmt="%a, %d %b %Y %H:%M:%S"))
        root_logger.addHandler(handler)

def disable():
    logger = logging.getLogger()
    logger.disabled = True
