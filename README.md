Rule Downloader
===============

This is a tool to aid in the downloading and archival of Snort
rulesets.  It also includes a tool, rulechanges.py to itemize the
changes from one version of a ruleset to another.

Configuration
-------------

The ruledownloader is configured with an INI style file.  The
configuration file is passed to the ruledownloader with the -c command
line switch.  Alternatively, the ruledownloader will look for a file
named ruledownloader.conf in the current directory and use that.

### Example Configuration

    [general]
    
    # The dest-dir parameter tells ruledownloader where to place the
    # files it downloads.  Subdirectories will be created under this
    # directory for each conifgured ruleset.
    dest-dir = .
    
    # A ruleset configuration for a VRT subscription ruleset for Snort
    # 2.9.0.4.
    [ruleset vrt-subscription-2904]

    # Set to no to skip downloading this ruleset.
    enabled = yes

    # The URL this ruleset is found at.
    url = http://www.snort.org/sub-rules/snortrules-snapshot-2904.tar.gz/<yourOinkCodeHere>
    
    # Another ruleset configuration.
    [ruleset et-open-290]
    enabled = yes
    url = http://rules.emergingthreats.net/open/snort-2.9.0/emerging.rules.tar.gz

Directory Structure
-------------------

Within the configured destination directory each policy will get its
own directory based on on the name of the policy.  That directory will
contained timestamped directory names based on when the ruleset was
downloaded.  A symlink names 'latest' will point to the most recently
downloader version of the ruleset.

### Example

Given the et-open-290 ruleset configuration above the following
directory structure will be created.

    ./et-open-290/201104070917/emerging.rules.tar.gz
    ./et-open-290/201104071531/emerging.rules.tar.gz
    ./et-open-209/latest -> 201104070917

Reporting Changes
-----------------

The rulechanges script can report the difference between an old and
new version of a ruleset.

### Usage:

    ./rulechanges.py <oldRuleset.tar.gz> <newRuleset.tar.gz>
