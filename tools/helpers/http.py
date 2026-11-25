# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import http.client
import logging
import os
import shutil
import socket
import ssl
import threading
import urllib.request

import tools.helpers.run
import time

# Seconds without any data before a connection is considered dead
DOWNLOAD_TIMEOUT = 60
# Attempts in a row that make no progress before giving up
DOWNLOAD_RETRIES = 5
DOWNLOAD_RETRY_DELAY = 5


def download(args, url, prefix, cache=True, loglevel=logging.INFO,
             allow_404=False):
    """ Download a file to disk.

        :param url: the http(s) address of to the file to download
        :param prefix: for the cache, to make it easier to find (cache files
                       get a hash of the URL after the prefix)
        :param cache: if True, and url is cached, do not download it again
        :param loglevel: change to logging.DEBUG to only display the download
                         message in 'waydroid log', not in stdout. We use
                         this when downloading many APKINDEX files at once, no
                         point in showing a dozen messages.
        :param allow_404: do not raise an exception when the server responds
                          with a 404 Not Found error. Only display a warning on
                          stdout (no matter if loglevel is changed).
        :returns: path to the downloaded file in the cache or None on 404 """

    # helper functions for progress
    def fromBytesToMB(numBytes, decimalPlaces=2):
        return round(int(numBytes)/1000000, decimalPlaces)

    def getDownloadSpeed(lastSize, currentSize, timeTaken, decimalPlaces=2):
        # sizes are in MB and timeTaken in seconds
        speedUnit = "MB/s"
        sizeDifference = currentSize-lastSize

        if sizeDifference < 1:
            # sizeDifference is less than 1 MB
            # convert sizeDifference to kB and speedUnit to kB/s,
            # for better readability
            sizeDifference*=1000
            speedUnit = "kB/s"

        # sizeDifference MB(or kB) was downloaded in timeTaken seconds
        # so downloadSpeed = sizeDifference/timeTaken MB/s(or kB/s)
        return (round(sizeDifference/timeTaken, decimalPlaces), speedUnit)

    # Show progress while downloading
    state = {"total": None, "paused": False, "line": False}
    downloadEnded = threading.Event()
    printLock = threading.Lock()
    def progress(destinationPath):
        # lastSize and lastSizeChangeAt is used to calculate speed
        lastSize = 0
        lastSizeChangeAt = time.time()

        while not downloadEnded.wait(2):
            # the file may not exist yet, or may have been removed
            # by another waydroid process
            try:
                currentSize = fromBytesToMB(os.path.getsize(destinationPath))
            except OSError:
                currentSize = 0

            sizeChangeAt = time.time()
            downloadSpeed = getDownloadSpeed(
                lastSize, max(currentSize, lastSize),
                timeTaken=sizeChangeAt-lastSizeChangeAt
            )

            lastSize = currentSize
            lastSizeChangeAt = sizeChangeAt

            if state["total"]:
                totalSize = fromBytesToMB(state["total"])
            else:
                totalSize = "?"
            # this value will be used to figure out maximum chars
            # required to denote downloaded size later on
            totalSizeStrLen = len(str(totalSize))

            # make currentSize and downloadSpeed of a fix max len,
            # to avoid previously printed chars to appear while \
            # printing recursively
            currentSize = str(currentSize).rjust(totalSizeStrLen)
            # assuming max downloadSpeed to be 9999.99 MB/s
            downloadSpeed = f"{str(downloadSpeed[0]).rjust(7)} {downloadSpeed[1]}"

            # print progress bar
            with printLock:
                if not state["paused"]:
                    print(f"\r[Downloading] {currentSize} MB/{totalSize} MB    {downloadSpeed}(approx.)", end=" ")
                    state["line"] = True

    def endProgressLine():
        if state["line"]:
            print()
            state["line"] = False

    # Create cache folder
    if not os.path.exists(args.work + "/cache_http"):
        tools.helpers.run.user(args, ["mkdir", "-p", args.work + "/cache_http"])

    # Check if file exists in cache
    prefix = prefix.replace("/", "_")
    path = (args.work + "/cache_http/" + prefix + "_" +
            hashlib.sha256(url.encode("utf-8")).hexdigest())
    if os.path.exists(path):
        if cache:
            return path
        tools.helpers.run.user(args, ["rm", path])

    # Download into a .part file, which is kept on failure so that the next
    # attempt (or the next run) can resume it with a Range request. It is only
    # renamed to the final path once the server says the transfer is complete;
    # callers still verify the checksum.
    part = path + ".part"
    logging.log(loglevel, "Downloading " + url)
    progressThread = threading.Thread(target=progress, args=(part,), daemon=True)
    progressThread.start()
    failures = 0
    try:
        while True:
            offset = os.path.getsize(part) if os.path.exists(part) else 0
            try:
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
                    content_range = response.headers.get("Content-Range", "")
                    length = response.headers.get("Content-Length")
                    if response.status == 206:
                        if not content_range.startswith(f"bytes {offset}-"):
                            os.remove(part)
                            raise ConnectionError(f"unexpected Content-Range: {content_range}")
                        mode = "ab"
                        total = content_range.rpartition("/")[2]
                        total = int(total) if total.isdigit() else None
                    else:
                        # The server ignored the range: start over
                        mode = "wb"
                        offset = 0
                        total = int(length) if length else None
                    if total is None and length:
                        total = offset + int(length)
                    state["total"] = total
                    with open(part, mode) as handle:
                        shutil.copyfileobj(response, handle)
                size = os.path.getsize(part)
                if total is not None and size < total:
                    raise ConnectionError(f"connection closed at {size} of {total} bytes")
                break
            except urllib.error.HTTPError as e:
                if e.code == 404 and allow_404:
                    logging.warning("WARNING: file not found: " + url)
                    return None
                if e.code == 416 and offset:
                    # The partial file is not usable, start over
                    os.remove(part)
                elif e.code < 500:
                    raise
                error = e
            except (socket.timeout, ConnectionError, http.client.HTTPException,
                    ssl.SSLError, urllib.error.URLError) as e:
                error = e
            new_offset = os.path.getsize(part) if os.path.exists(part) else 0
            failures = 0 if new_offset > offset else failures + 1
            if failures >= DOWNLOAD_RETRIES:
                raise error
            with printLock:
                state["paused"] = True
                endProgressLine()
                logging.warning(f"Download interrupted ({error}), retrying in "
                                f"{DOWNLOAD_RETRY_DELAY} seconds...")
            time.sleep(DOWNLOAD_RETRY_DELAY)
            state["paused"] = False
    finally:
        downloadEnded.set()
        progressThread.join()
        endProgressLine()

    os.replace(part, path)

    # Return path in cache
    return path


def retrieve(url, headers=None):
    """ Fetch the content of a URL and returns it as string.

        :param url: the http(s) address of to the resource to fetch
        :param headers: dict of HTTP headers to use
        :returns: status and str with the content of the response
    """
    # Download the file
    logging.verbose("Retrieving " + url)

    if headers is None:
        headers = {}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
            return 200, response.read()
    # Handle malformed URL
    except ValueError:
        return -1, ""
    # Handle 404
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, socket.timeout, ConnectionError):
        return -2, ""
