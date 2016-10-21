#!/usr/bin/env python

# Copyright (c) 2016, Palo Alto Networks
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Author: Brian Torres-Gil <btorres-gil@paloaltonetworks.com>

# Changes
# 2016-10 Tor Mogstad <torm@datequipment.no>
# Added varibale and methods to support download of software updates
#  - Added global varaible in class ContentDownloader named SOFTWARE_URL
#  - Added methods in class ContentDownloader named get_all_releases and download_software

"""Palo Alto Networks dynamic content update downloader

Downloads the latest content packs from paloaltonetworks.com.

This software is provided without support, warranty, or guarantee.
Use at your own risk.

Works with python 2.7 only.
"""

from __future__ import print_function
import os
import sys
import re
import cookielib
import logging
import ConfigParser
import argparse

import mechanize
# Disable insecure platform warnings
#import requests.packages.urllib3
#requests.packages.urllib3.disable_warnings()

class LoginError(StandardError):
    pass

class UpdateError(StandardError):
    pass

class UnknownPackage(StandardError):
    pass

class ContentDownloader(object):
    """Checks for new content packages and downloads the latest"""

    """This PACKAGE variable can be modified to reflect any changes in the URL's or
    to add additional packages as they come available. It is a basic python
    dictionary where the key is the string usually passed as a command line
    argument to specify a package, and the value is the part of the file download
    URL between the hostname and the package version. For example, a download URL
    takes the form:

        https://downloads.paloaltonetworks.com/content/panupv2-all-contents-578-2874

    The value in the PACKAGE dict should be the part between the
    'downloads.paloaltonetworks.com/' and the '-578-2874' (the version).

    Maintenance of this script involves keeping these values up-to-date with the actual
    URL to download the file.
    """
    PACKAGE = {
        "appthreat": "content/panupv2-all-contents",
        "app":       "content/panupv2-all-apps",
        "antivirus": "virus/panup-all-antivirus",
        "wildfire":  "wildfire/panup-all-wildfire",
        "wildfire2": "wildfire/panupv2-all-wildfire",
    }

    SUPPORT_URL = "https://support.paloaltonetworks.com"
    UPDATE_URL = "https://support.paloaltonetworks.com/Updates/DynamicUpdates"
    SOFTWARE_URL = "https://support.paloaltonetworks.com/Updates/SoftwareUpdates/"
    
    def __init__(self, username, password, package="appthreat", debug=False):
        if package is None:
            package = "appthreat"
        if package not in self.PACKAGE:
            raise UnknownPackage("Unknown package type: %s" % package)
        self.username = username
        self.password = password
        self.package = package
        self.path = self.PACKAGE[package]
        self.prefix = self.path.split("/")[-1]
        self.latestversion = None
        self.fileurl = None
        self.cj = cookielib.LWPCookieJar()
        try:
            self.cj.load("cookies.txt", ignore_discard=True, ignore_expires=True)
        except IOError:
            # Ignore if there are no cookies to load
            logging.debug("No existing cookies found")
            pass
        self.browser = self.get_browser(debug)

    def get_browser(self, debug=False):
        br = mechanize.Browser()
        # Cookie Jar
        br.set_cookiejar(self.cj)
        # Browser options
        br.set_handle_equiv(True)
        #br.set_handle_gzip(True)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.set_handle_robots(False)
        br.addheaders = [
            ("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36"),
        ]
        if debug:
            br.set_debug_http(True)
            br.set_debug_redirects(True)
            br.set_debug_responses(True)
        return br

    def login(self):
        logging.info("Logging in")
        self.browser.open(self.SUPPORT_URL)
        self.browser.select_form(nr=0)
        self.browser.form['Email'] = self.username
        self.browser.form['Password'] = self.password
        self.browser.submit()
        # No Javascript, so have to submit the "Resume form"
        self.browser.select_form(nr=0)
        self.browser.submit()
        html = self.browser.response().read()
        if html.find("Welcome") == -1:
            raise LoginError("Failed to login")
        # Save login cookie
        self._save_cookies()

    def check(self):
        logging.info("Checking for new content updates: %s" % self.package)
        result = self._check()
        needlogin = False
        if result.find("<h1>Single Sign On</h1>") != -1:
            needlogin = True
            logging.debug("Got single sign on page")
        elif result.find("<h4>You are not authorized to perform this action.</h4>") != -1:
            needlogin = True
            logging.debug("Got not authorized page")
        if needlogin:
            logging.info("Not logged in.")
            self.login()
            logging.info("Checking for new content updates (2nd attempt)")
            result = self._check()
        file_url = "https://downloads.paloaltonetworks.com/" + self.path
        try:
            # Grab the first link that matches the regex,
            # which is the download link for the first dynamic update
            url = list(self.browser.links(url_regex=file_url))[0].url
        except IndexError:
            raise UpdateError("Unable to get content update list")
        # Add the version to the regex to extract the latest version number
        file_regex = file_url + "-([\d-]*)\?"
        # Get the version
        version = re.search(file_regex, url).group(1)
        self.latestversion = version
        self.fileurl = url
        return version, url

    def _check(self):
        self.browser.open(self.UPDATE_URL)
        return self.browser.response().read()

    def download(self, download_dir):
        if self.latestversion is not None and self.fileurl is not None:
            os.chdir(download_dir)
            filename = self.prefix+"-"+self.latestversion
            self.browser.retrieve(self.fileurl, filename)
            return filename

    def _save_cookies(self):
        self.cj.save("cookies.txt", ignore_discard=True, ignore_expires=True)
        
    def get_all_releases(self):
        logging.info("Checking for available main releases:")
        result = self._check_software()
        needlogin = False
        if result.find("<h1>Single Sign On</h1>") != -1:
            needlogin = True
            logging.debug("Got single sign on page")
        elif result.find("<h4>You are not authorized to perform this action.</h4>") != -1:
            needlogin = True
            logging.debug("Got not authorized page")
        elif result.find("An unexpected error has occurred.") != -1:
            needlogin = True
            logging.debug("Got unexpected error page")
        if needlogin:
            logging.info("Not logged in.")
            self.login()
            logging.info("Checking for new content updates (2nd attempt)")
            result = self._check_software()
        download_regex = "https://downloads.paloaltonetworks.com/software"
        logging.info(download_regex)
        try:
            releases = list(self.browser.links(url_regex=download_regex))
        except IndexError:
            raise UpdateError("Unable to get content update list")
        release_list = []
        for release in releases:
            link = release.url
            text = release.text
            if ".pdf" in text: continue # This is release notes, which we don't want.
            else:
                this_release = [text,link]
                release_list.append(this_release)
        return release_list

    def _check_software(self):
        self.browser.open(self.SOFTWARE_URL)
        temp = self.browser.response().read()
        logging.info(temp)
        return temp

    def download_software(self, download_dir,url):
        os.chdir(download_dir)
        filename = url.split("/")
        filename = filename[len(filename)-1]
        filename = filename.split("?")[0]
        self.browser.retrieve(url,filename)
        return filename

    
def get_config(filename):
    config = ConfigParser.SafeConfigParser({"filedir": ""})
    config.read(filename)
    username = config.get('config', 'username')
    password = config.get('config', 'password')
    download_dir = config.get('config', 'filedir')
    if download_dir == "":
        download_dir = os.getcwd()
    return username, password, download_dir


def parse_arguments():
    parser = argparse.ArgumentParser(description='Download the latest Palo Alto Networks dynamic content update')
    parser.add_argument('-v', '--verbose', action='count', help="Verbose (-vv for extra verbose)")
    parser.add_argument('-p', '--package', help="Options: appthreat, app, antivirus, wildfire (for PAN-OS 7.0 and"
                                                " lower), or wildfire2 (for PAN-OS 7.1 and higher). If ommited, "
                                                "defaults to 'appthreat'.")
    return parser.parse_args()


def enable_logging(options):
    # Logging
    if options.verbose is not None:
        if options.verbose == 1:
            logging_level = logging.INFO
            logging_format = ' %(message)s'
        else:
            logging_level = logging.DEBUG
            logging_format = '%(levelname)s: %(message)s'
        logging.basicConfig(format=logging_format, level=logging_level)
    return True if options.verbose > 1 else False


def main():
    # Parse CLI arguments
    options = parse_arguments()
    # Enable logging
    debugenabled = enable_logging(options)

    # Config file (for support account credentials)
    username, password, download_dir = get_config('content_downloader.conf')

    # Create contentdownloader object
    content_downloader = ContentDownloader(username=username, password=password, package=options.package, debug=debugenabled)

    # Check latest version. Login if necessary.
    latestversion, fileurl = content_downloader.check()

    # Get previously downloaded versions from download directory
    downloaded_versions = []
    for f in os.listdir(download_dir):
        match = re.match(content_downloader.prefix + "-([\d-]*)$", f)
        if match is not None:
            downloaded_versions.append(match.group(1))

    # Check if already downloaded latest and do nothing
    if latestversion in downloaded_versions:
        logging.info("Already downloaded latest version: %s" % latestversion)
        sys.exit(0)

    # Download latest version to download directory
    logging.info("Downloading latest version: %s" % latestversion)
    filename = content_downloader.download(download_dir)
    if filename is not None:
        logging.info("Finished downloading file: %s" % filename)
    else:
        logging.error("Unable to download latest content update")


# Call the main() function to begin the program if not
# loaded as a module.
if __name__ == '__main__':
    main()
