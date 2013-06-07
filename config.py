###
# Copyright (c) 2012-2013, spline
# All rights reserved.
#
#
###

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
conf.registerGlobalValue(MLB, 'logURLs', registry.Boolean(True, """Should we log all URL calls?"""))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=250:
