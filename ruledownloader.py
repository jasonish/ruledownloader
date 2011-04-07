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
import tempfile
import shutil

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
    rulesets = {}
    for r in [r.strip() for r in config.get("general", "rulesets").split(",")]:
        section = "ruleset %s" % r
        if config.has_section(section):
            if config.getboolean(section, "enabled"):
                rulesets[r] = {}
                rulesets[r]["name"] = r
                rulesets[r]["url"] = config.get(section, "url")
    return rulesets

def downloadRuleset(ruleset):
    name = ruleset["name"]
    url = ruleset["url"]
    filename = extractFilenameFromUrl(ruleset["url"])
    remoteMd5 = None
    latestFilename = "%s/%s/latest/%s" % (destdir, name, filename)
    if os.path.exists(latestFilename):
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
        tmpDestFile, headers = urllib.urlretrieve(url)
        logging.debug("Downloaded to %s.", tmpDestFile)
    except Exception, e:
        logging.error("Failed to download %s.", url)
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
    if os.path.exists(latestFilename):
        latestMd5 = getFileMd5(latestFilename)
        newMd5 = getFileMd5(tmpDestFile)
        if latestMd5 == newMd5:
            logging.debug("Ruleset has not changed, discarding download.")
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

def usage(output):
    print >>output, ""
    print >>output, "USAGE: %s [options] [ruleset]" % sys.argv[0]
    print >>output, ""
    print >>output, "    Options:"
    print >>output, "        -c <filename> Configuration file."
    print >>output, "        -D            Enable debug output."
    print >>output, ""
    print >>output, """\
    If one or more ruleset names are provided on the command then they will
    be the only ones checked for updates."""
    print >>output, ""

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
        level=logLevel, format="[%(asctime)s] %(levelname)-6s: %(message)s")

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
            continue
        logging.info("Processing ruleset %s.", key)
        downloadRuleset(rulesets[key])

if __name__ == '__main__':
    sys.exit(main())
