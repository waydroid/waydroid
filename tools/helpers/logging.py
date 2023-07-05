# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import sys


class log_handler(logging.StreamHandler):
    """
    Write to stdout and to the already opened log file.
    """
    _args = None

    def emit(self, record):
        try:
            msg = self.format(record)

            # INFO or higher: Write to stdout
            if (not self._args.details_to_stdout and
                not self._args.quiet and
                    record.levelno >= logging.INFO):
                stream = self.stream
                stream.write(msg)
                stream.write(self.terminator)
                self.flush()

            # Everything: Write to logfd
            msg = "(" + str(os.getpid()).zfill(6) + ") " + msg
            self._args.logfd.write(msg + "\n")
            self._args.logfd.flush()

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
    """
    Set log format and add the log file descriptor to args.logfd, add the
    verbose log level.
    """
    # Set log file descriptor (logfd)
    if args.details_to_stdout:
        setattr(args, "logfd", sys.stdout)
    else:
        # Require containing directory to exist (so we don't create the work
        # folder and break the folder migration logic, which needs to set the
        # version upon creation)
        dir = os.path.dirname(args.log)
        if os.path.exists(dir):
            setattr(args, "logfd", open(args.log, "a+"))
            try:
                os.chmod(args.log, 0o666)
            except PermissionError:
                pass
        else:
            setattr(args, "logfd", open(os.devnull, "a+"))
            if args.action != "init":
                print("WARNING: Can't create log file in '" + dir + "', path"
                      " does not exist!")

    # Set log format
    root_logger = logging.getLogger()
    root_logger.handlers = []
    formatter = logging.Formatter("[%(asctime)s] %(message)s",
                                  datefmt="%H:%M:%S")

    # Set log level
    add_verbose_log_level()
    root_logger.setLevel(logging.DEBUG)
    if args.verbose:
        root_logger.setLevel(logging.VERBOSE)

    # Add a custom log handler
    handler = log_handler()
    log_handler._args = args
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def disable():
    logger = logging.getLogger()
    logger.disabled = True
