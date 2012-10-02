###
# Copyright (c) 2012, spline
# All rights reserved.
#
#
###

import os

import supybot.conf as conf
import supybot.registry as registry
from supybot.i18n import PluginInternationalization, internationalizeDocstring

_ = PluginInternationalization('MLB')

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('MLB', True)


MLB = conf.registerPlugin('MLB')
# This is where your configuration variables (if any) should go.  For example:
conf.registerGlobalValue(MLB, 'dbLocation', registry.String(os.path.abspath(os.path.dirname(__file__)) + '/mlb.db', _("""Absolute path for mlb.db sqlite3 database file location.""")))
conf.registerGlobalValue(MLB, 'ffApiKey', registry.String('', """api key for fanfeedr.com""", private=True))
conf.registerGlobalValue(MLB, 'usatApiKey', registry.String('', """api key for developer.usatoday.com""", private=True))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=250:
