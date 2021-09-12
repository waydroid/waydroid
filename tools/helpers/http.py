# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import logging
import os
import shutil
import urllib.request

import tools.helpers.run


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
    logging.log(loglevel, "Download " + url)
    try:
        with urllib.request.urlopen(url) as response:
            with open(path, "wb") as handle:
                shutil.copyfileobj(response, handle)
    # Handle 404
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            logging.warning("WARNING: file not found: " + url)
            return None
        raise

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

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return 200, response.read()
    # Handle 404
    except urllib.error.HTTPError as e:
        return e.code, ""
