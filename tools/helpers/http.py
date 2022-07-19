# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import logging
import os
import shutil
import threading
import urllib.request

import tools.helpers.run
import time


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
        # sizes are in mb and timeTaken in seconds
        speedUnit = "mbps"
        sizeDifference = currentSize-lastSize

        if sizeDifference < 1:
            # sizeDifference is less than 1 mb
            # convert sizeDifference to kb and speedUnit to kbps,
            # for better readability
            sizeDifference*=1000
            speedUnit = "kbps"
        
        # sizeDifference mb(or kb) was downloaded in timeTaken seconds
        # so downloadSpeed = sizeDifference/timeTaken mbps(or kbps)
        return (round(sizeDifference/timeTaken, decimalPlaces), speedUnit)

    # Show progress while downloading
    downloadEnded = False
    def progress(totalSize, destinationPath):
        # convert totalSize to mb before hand,
        # it's value won't change inside while loop and
        # will be unnecessarily calculated every .01 seconds 
        totalSize = fromBytesToMB(totalSize)

        # this value will be used to figure out maximum chars
        # required to denote downloaded size later on
        totalSizeStrLen = len(str(totalSize))

        # lastSize and lastSizeChangeAt is used to calculate speed
        lastSize = 0
        lastSizeChangeAt = time.time()

        downloadSpeed = 0, "mbps"

        while not downloadEnded:
            currentSize = fromBytesToMB(os.path.getsize(destinationPath))
            
            if currentSize != lastSize:
                sizeChangeAt = time.time()
                downloadSpeed = getDownloadSpeed(
                    lastSize, currentSize,
                    timeTaken=sizeChangeAt-lastSizeChangeAt
                )

                lastSize = currentSize
                lastSizeChangeAt = sizeChangeAt

                # make currentSize and downloadSpeed of a fix max len,
                # to avoid previously printed chars to appear while \
                # printing recursively
                # currentSize is not going to exceed totalSize
                currentSize = str(currentSize).rjust(totalSizeStrLen)
                # assuming max downloadSpeed to be 9999.99 mbps
                downloadSpeed = f"{str(downloadSpeed[0]).rjust(7)} {downloadSpeed[1]}"
                
                # print progress bar
                print(f"\r[Downloading] {currentSize} MB/{totalSize} MB    {downloadSpeed}(approx.)", end=" ")
            time.sleep(.01)

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

    # Download the file
    logging.log(loglevel, "Downloading " + url)
    try:
        with urllib.request.urlopen(url) as response:
            with open(path, "wb") as handle:
                # adding daemon=True will kill this thread if main thread is killed
                # else progress_bar will continue to show even if user cancels download by ctrl+c
                threading.Thread(target=progress, args=(response.headers.get('content-length'), path), daemon=True).start()
                shutil.copyfileobj(response, handle)
    # Handle 404
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            logging.warning("WARNING: file not found: " + url)
            return None
        raise
    downloadEnded = True

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
        with urllib.request.urlopen(req) as response:
            return 200, response.read()
    # Handle malformed URL
    except ValueError as e:
        return -1, ""
    # Handle 404
    except urllib.error.HTTPError as e:
        return e.code, ""
