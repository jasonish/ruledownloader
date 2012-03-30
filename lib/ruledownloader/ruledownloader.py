#! /usr/bin/env python
#
# The MIT License
#
# Copyright (c) Jason Ish
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import os
import os.path
import time
import ConfigParser
import urllib2
import urllib
import logging
import hashlib
import re
import getopt
import shutil
import string

try:
    import progressbar
    has_progressbar = True
except:
    has_progressbar = False

import rulechanges

valid_content_types = ["application/x-gzip",
                       "application/x-tar",
                       "application/octet-stream",
                       "binary/octet-stream"]

class NullProgressMeter(object):

    def update(self, transferred, block_size, total_size):
        pass

    def done(self):
        pass

class FancyProgressMeter(object):

    def __init__(self):
        self.bar = progressbar.ProgressBar(
            widgets=[progressbar.Percentage(),
                     progressbar.Bar()],
            maxval=100)
        self.bar.start()

    def update(self, transferred, block_size, total_size):
        val = int((transferred * block_size) / float(total_size) * 100)
        self.bar.update(val)

    def done(self):
        self.bar.finish()

def get_progress_meter():
    if not sys.stdout.isatty():
        return NullProgressMeter()
    elif has_progressbar:
        return FancyProgressMeter()
    else:
        return NullProgressMeter()

def getFileMd5(filename):
    """ Return the hex md5 of the given filename. """
    m = hashlib.md5()
    m.update(open(filename).read())
    return m.hexdigest()

def extractFilenameFromUrl(url):
    """ Extract a filename from a URL. """
    validExts = [".tar.gz", ".tar.bz2", ".zip"]
    for part in url.split("/"):
        for ext in validExts:
            if part.endswith(ext):
                return part
    return None

def getRemoteMd5(url):
    """ Get the MD5 of the remote file.  Note that this assumes that
    the MD5 is in the remote filename with .md5 appended. """
    logging.info("Downloading %s.", url)
    try:
        remote = urllib2.urlopen(url)
    except urllib2.URLError, err:
        logging.error("Failed to download MD5 URL: %s", err)
        return None
    output = remote.read()
    m = re.search("([a-zA-Z0-9]+)", output)
    if m:
        return m.group(1)
    else:
        return None

def getRulesets():
    """ Get the set of configured rulesets. """

    rulesets = {}

    for section in [s for s in config.sections() if s.startswith("ruleset ")]:
        name = string.split(section, " ", maxsplit=1)[1]
        if config.has_section(section):
            if config.getboolean(section, "enabled"):
                rulesets[name] = {}
                rulesets[name]["name"] = name
                rulesets[name]["url"] = config.get(section, "url")
    return rulesets

def download_ruleset(ruleset):
    name = ruleset["name"]
    url = ruleset["url"]
    filename = extractFilenameFromUrl(ruleset["url"])
    remoteMd5 = None

    latest = None
    latestFilename = None
    if os.path.exists("%s/%s/latest" % (destdir, name)):
        latest = os.readlink("%s/%s/latest" % (destdir, name))
        latestFilename = "%s/%s/%s/%s" % (destdir, name, latest, filename)

    if latestFilename and os.path.exists(latestFilename):
        md5Url = url.replace(filename, filename + ".md5")
        remoteMd5 = getRemoteMd5(md5Url)
        if not remoteMd5:
            logging.info("Remote ruleset hash not available, will download.")
        elif remoteMd5 == getFileMd5(latestFilename):
            logging.info("Remote ruleset has not changed, will not download.")
            return
        else:
            logging.info("Remote ruleset hash has changed, will download.")
    else:
        logging.debug("%s does not exist, will not check MD5.", latestFilename)

    destFile = "%s/%s/%s/%s" % (destdir, name, timestamp, filename)
    if not os.path.exists(os.path.dirname(destFile)):
        logging.debug("Creating directory %s.", os.path.dirname(destFile))
        os.makedirs(os.path.dirname(destFile))
    logging.info("Downloading %s to %s.", url, destFile)
    try:
        meter = get_progress_meter()
        tmpDestFile, headers = urllib.urlretrieve(url, reporthook=meter.update)
        meter.done()
        logging.debug("Downloaded to %s.", tmpDestFile)
    except Exception, e:
        logging.error("Failed to download %s.", url)
        raise

    if headers["content-type"] not in valid_content_types:
        logging.error("Invalid content type: %s", headers["content-type"])
        return

    tmpMd5 = getFileMd5(tmpDestFile)

    if remoteMd5:
        logging.info("Verifying checksum.")
        if tmpMd5 == remoteMd5:
            logging.info("OK.")
        else:
            logging.info("FAIL.")
            return

    # Compare to the last file.
    if latestFilename and os.path.exists(latestFilename):
        latestMd5 = getFileMd5(latestFilename)
        newMd5 = getFileMd5(tmpDestFile)
        if latestMd5 == newMd5:
            logging.info("Ruleset has not changed, discarding download.")
            return

    logging.debug("Copying %s to %s.", tmpDestFile, destFile)
    shutil.copy(tmpDestFile, destFile)

    # Write out the md5.
    open(destFile + ".md5", "w").write(tmpMd5)

    # Update symlink.
    logging.debug("Updating latest symlink to %s/%s.", destdir, name)
    latestLink = "%s/%s/latest" % (destdir, name)
    if os.path.exists(latestLink):
        os.unlink(latestLink)
    os.symlink(timestamp, latestLink)

    # Generate a report.
    if latestFilename and os.path.exists(latestFilename):
        report_filename = "%s/%s/latest/change_log.txt" % (
            destdir, name)
        logging.info("Writing change report to %s." % (report_filename))
        with open(report_filename, "w") as report_out:
            rulechanges.main(
                (latestFilename, "%s/%s" % (latestLink, filename)),
                report_out)

def usage(output):
    print >>output, """
USAGE: %s [options] [ruleset]

Options:
        -c <filename> Configuration file.
        -D            Enable debug output.

If one or more ruleset names are provided on the command then they will
be the only ones checked for updates.
""" % sys.argv[0]

def main():
    global config
    global destdir
    global timestamp

    configFilename = "ruledownloader.conf"
    logLevel = logging.INFO
    try:
        opts, args = getopt.getopt(sys.argv[1:], "Dc:h", [])
    except getopt.GetoptError, err:
        print >>sys.stderr, "ERROR: " + str(err)
        usage(sys.stderr)
        return 1
    for o, a in opts:
        if o == "-c":
            configFilename = a
        elif o == "-h":
            usage(sys.stdout)
            return 0
        elif o == "-D":
            logLevel = logging.DEBUG
    selectedRulesets = args

    logging.basicConfig(
        level=logLevel, format="[%(asctime)s] %(levelname)-6s: %(message)s",
        stream=sys.stdout)

    if not os.path.exists(configFilename):
        logging.error("Configuration file does not exist: %s", configFilename)
        return 1
    config = ConfigParser.ConfigParser(defaults=os.environ)
    config.read(configFilename)

    timestamp = time.strftime("%Y%m%d%H%M", time.localtime())
    destdir = os.path.realpath(config.get("general", "dest-dir"))
    logging.debug("Using destination directory %s", destdir)

    rulesets = getRulesets()
    for key in rulesets:
        if selectedRulesets and key not in selectedRulesets:
            logging.debug("Skipping ruleset %s.", key)
        else:
            logging.info("Processing ruleset %s.", key)
            download_ruleset(rulesets[key])

if __name__ == '__main__':
    sys.exit(main())
