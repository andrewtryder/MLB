# -*- coding: utf-8 -*-
###
# see LICENSE.txt for information.
###

# my libs.
from BeautifulSoup import BeautifulSoup, Comment
from urllib import quote_plus
from lxml import html
import requests
import re
import collections
import datetime
import random
import sqlite3
from itertools import groupby, count
import os.path
from base64 import b64decode
import jellyfish  # similar players.
from operator import itemgetter  # similar players.
# supybot libs.
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization, internationalizeDocstring

_ = PluginInternationalization('MLB')

@internationalizeDocstring
class MLB(callbacks.Plugin):
    """Add the help for "@plugin help MLB" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        self.__parent = super(MLB, self)
        self.__parent.__init__(irc)
        self._mlbdb = os.path.abspath(os.path.dirname(__file__)) + '/db/mlb.db'

    def die(self):
        self.__parent.die()

    ##############
    # FORMATTING #
    ##############

    def _red(self, string):
        """Returns a red string."""
        return ircutils.mircColor(string, 'red')

    def _yellow(self, string):
        """Returns a yellow string."""
        return ircutils.mircColor(string, 'yellow')

    def _green(self, string):
        """Returns a green string."""
        return ircutils.mircColor(string, 'green')

    def _bold(self, string):
        """Returns a bold string."""
        return ircutils.bold(string)

    def _blue(self, string):
        """Returns a blue string."""
        return ircutils.mircColor(string, 'blue')

    def _ul(self, string):
        """Returns an underline string."""
        return ircutils.underline(string)

    def _bu(self, string):
        """Returns a bold/underline string."""
        return ircutils.bold(ircutils.underline(string))

    ######################
    # INTERNAL FUNCTIONS #
    ######################

    def _splicegen(self, maxchars, stringlist):
        """Return a group of splices from a list based on the maxchars
        string-length boundary.
        """

        runningcount = 0
        tmpslice = []
        for i, item in enumerate(stringlist):
            runningcount += len(item)
            if runningcount <= int(maxchars):
                tmpslice.append(i)
            else:
                yield tmpslice
                tmpslice = [i]
                runningcount = len(item)
        yield(tmpslice)

    def _batch(self, iterable, size):
        """http://code.activestate.com/recipes/303279/#c7"""

        c = count()
        for k, g in groupby(iterable, lambda x: c.next()//size):
            yield g

    def _validate(self, date, format):
        """Return true or false for valid date based on format."""

        try:
            datetime.datetime.strptime(str(date), format)  # format = "%m/%d/%Y"
            return True
        except ValueError:
            return False

    def _httpget(self, url, h=None, d=None, l=True):
        """General HTTP resource fetcher. Pass headers via h, data via d, and to log via l."""

        if self.registryValue('logURLs') and l:
            self.log.info(url)

        try:
            if h and d:
                page = utils.web.getUrl(url, headers=h, data=d)
            else:
                h = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:17.0) Gecko/20100101 Firefox/17.0"}
                h = {'User-Agent': "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:38.0) Gecko/20100101 Firefox/38.0"}
                page = utils.web.getUrl(url, headers=h)
            return page
        except Exception as e:
            self.log.error("ERROR opening {0} message: {1}".format(url, e))
            return None

    def _b64decode(self, string):
        """Returns base64 decoded string."""

        return b64decode(string)

    def _dtFormat(self, outfmt, instring, infmt):
        """Convert from one dateformat to another."""

        try:
            d = datetime.datetime.strptime(instring, infmt)
            output = d.strftime(outfmt)
        except:
            output = instring
        return output

    ######################
    # DATABASE FUNCTIONS #
    ######################

    def _allteams(self):
        """Return a list of all valid teams (abbr)."""

        with sqlite3.connect(self._mlbdb) as conn:
            cursor = conn.cursor()
            query = "SELECT team FROM mlb"
            cursor.execute(query)
            teamlist = [item[0] for item in cursor.fetchall()]

        return " | ".join(sorted(teamlist))

    def _validteams(self, optteam):
        """Takes optteam as input function and sees if it is a valid team.
        Aliases are supported via mlbteamaliases table.
        Returns a 1 upon error (no team name nor alias found.)
        Returns the team's 3-letter (ex: NYY or ARI) if successful."""

        with sqlite3.connect(self._mlbdb) as conn:
            cursor = conn.cursor()
            query = "SELECT team FROM mlbteamaliases WHERE teamalias=?"  # check aliases first.
            cursor.execute(query, (optteam.lower(),))
            aliasrow = cursor.fetchone()  # this will be None or the team (NYY).
            if not aliasrow:  # person looking for team.
                query = "SELECT team FROM mlb WHERE team=?"
                cursor.execute(query, (optteam.upper(),))  # standard lookup. go upper. nyy->NYY.
                teamrow = cursor.fetchone()
                if not teamrow:  # team is not found. Error.
                    returnval = None  # checked in each command.
                else:  # ex: NYY
                    returnval = str(teamrow[0])
            else:  # alias turns into team like NYY.
                returnval = str(aliasrow[0])
        # return time.
        return returnval

    def _translateTeam(self, db, column, optteam):
        """Translates optteam (validated via _validteams) into proper string using database column."""

        with sqlite3.connect(self._mlbdb) as conn:
            cursor = conn.cursor()
            query = "SELECT %s FROM mlb WHERE %s=?" % (db, column)
            cursor.execute(query, (optteam,))
            row = cursor.fetchone()

        return (str(row[0]))

    ####################
    # PUBLIC FUNCTIONS #
    ####################

    def mlbcountdown(self, irc, msg, args):
        """
        Display countdown until next MLB opening day.
        """

        oDate = {"year": 2016, "month": 04, "day": 04}
        stDate = {"year": 2016, "month": 02, "day": 17}
        oDay = (datetime.datetime(oDate["year"], oDate["month"], oDate["day"]) - datetime.datetime.now()).days
        pDay = (datetime.datetime(stDate["year"], stDate["month"], stDate["day"]) - datetime.datetime.now()).days
        irc.reply("{0} day(s) until {1} MLB Opening Day ({2}/{3}/{4}). {5} day(s) until pitchers and catchers report ({6}/{7}/{8}).".format(
            oDay, oDate["year"], oDate["month"], oDate["day"], oDate["year"], pDay, stDate["month"], stDate["day"], stDate["year"]))

    mlbcountdown = wrap(mlbcountdown)

    def springtraining(self, irc, msg, args):
        """
        Display countdown until spring training.
        """
        
        # change this values year to year (TODO: registry values)
        pcDate = {'year': 2016, 'month': 02, 'day': 17}
        fgDate = {'year': 2016, 'month': 03, 'day': 01}

        pcDateStr = '{0}/{1}/{2}'.format(pcDate['month'], pcDate['day'], pcDate['year'])
        fgDateStr = '{0}/{1}/{2}'.format(fgDate['month'], fgDate['day'], fgDate['year'])

        pcDays = (datetime.datetime(pcDate['year'], pcDate['month'], pcDate['day']) - datetime.datetime.now()).days
        fgDays = (datetime.datetime(fgDate['year'], fgDate['month'], fgDate['day']) - datetime.datetime.now()).days
        irc.reply("{0} day(s) until pitchers and catchers report ({1}). {2} day(s) until the first spring training game ({3}).".format(
            pcDays, pcDateStr, fgDays, fgDateStr))

    def mlbteams(self, irc, msg, args):
        """
        Display a list of valid teams for input.
        """

        irc.reply("Valid MLB teams are: {0}".format(self._allteams()))

    mlbteams = wrap(mlbteams)

    def mlbchanlineup(self, irc, msg, args):
        """
        Display a random lineup for channel users.
        """

        if not ircutils.isChannel(msg.args[0]):  # make sure its run in a channel.
            irc.reply("ERROR: Must be run from a channel.")
            return
        # now make sure we have more than 9 users.
        users = [i for i in irc.state.channels[msg.args[0]].users]
        if len(users) < 9:  # need >9 users.
            irc.reply("Sorry, I can only run this in a channel with more than 9 users.")
            return
        # now that we're good..
        positions = (['(SS)', '(CF)', '(2B)', '(RF)', '(DH)', '(C)', '(1B)', '(3B)', '(LF)'])
        random.shuffle(positions)  # shuffle.
        lineup = []  # list for output.
        for position in positions:  # iterate through and highlight.
            a = random.choice(users)  # pick a random user.
            users.remove(a)  # remove so its unique. append below.
            lineup.append("{0}{1}".format(self._bold(a), position))
        # now output.
        irc.reply("{0} ALL-STAR LINEUP :: {1}".format(self._red(msg.args[0]), ", ".join(lineup)))

    mlbchanlineup = wrap(mlbchanlineup)

    def mlbpitcher(self, irc, msg, args, optteam):
        """<team>
        Displays current pitcher(s) and stats in active or previous game for team.
        Ex: NYY
        """

        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build url and fetch scoreboard.
        url = "http://scores.nbcsports.com/mlb/scoreboard.asp"
        html = self._httpget(url)
        if not html: 
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process scoreboard.
        soup = BeautifulSoup(html)
        games = soup.select('table.shsTable.shsLinescore')
        # container to put all of the teams in.
        teamdict = collections.defaultdict(list)
        # process each "game" (two teams in each)
        for game in games:
            tns = game.find_all('a', class_='teamName')
            if tns:
                for n in tns:
                    tn = str(n.getText())
                    try:
                        gid = game.select('span.shsPreviewLink')
                        for g in gid:
                            gid = g.find('a', href=True)
                            gid = str(re.findall('\d+', gid['href'])).strip('\'[]')
                        tn = self._translateTeam('team', 'yname', tn)
                        teamdict[tn].append(gid)
                    except Exception as e:
                        self.log.info("ERROR :: mlbpitcher :: {0}".format(e))
                        pass
        # grab the gameid. fetch.
        teamgameids = teamdict.get(optteam)
        # sanity check before we grab the game.
        if not teamgameids:
            irc.reply("ERROR: No upcoming/active games with: {0}. Check closer to gametime.".format(optteam))
            return
        # TBD how to handle more than one game per team per day (doubleheaders)
        # if len(teamgameids) > 1:  # we have a doubleheader
        # fetch the game, for now will only fetch game 1 of a doubleheader
        url = "http://scores.nbcsports.com/mlb/boxscore.asp?gamecode=" + teamgameids[0]
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        soup = BeautifulSoup(html)
        # grab relevant pitching tables
        pitching = soup.select('table.shsTable.shsBorderTable')
        pitching = pitching[-2:]
        if not pitching:
            irc.reply("ERROR: I could not find pitching. Use command once game is active/finished.")
            return
        # process tables
        p = collections.defaultdict(list)
        for ptable in pitching:
            team = ptable.find('td', class_='shsNamD').getText()
            # translate the team.
            team = self._translateTeam('team', 'fulltrans', team)
            colhead = ptable.find('tr', class_='shsColTtlRow').find_all('td')
            cols = ptable.find_all('tr', attrs={'class': re.compile('shsRow\dRow')})
            t = []
            for col in cols:
                # extract name and stats. format for legibility
                pname = "{0} {1}".format(self._bold(self._blue(col.find('td').getText().split(',',1)[0])),'[')
                rest = " ".join([self._bold(colhead[k+1].getText()) + ": " + \
                                z.getText() for (k, z) in enumerate(col.find_all('td', class_='shsNumD'))])
                p[team].append("{0} {1} {2}".format(pname, rest, "]"))
        # output
        output = p.get(optteam)
        for item in output:
            irc.reply("{0}".format(item))

    mlbpitcher = wrap(mlbpitcher, [('somethingWithoutSpaces')])

    def mlbworldseries(self, irc, msg, args, optyear):
        """<YYYY>
        Display results for a MLB World Series that year. Earliest year is 1903 and latest is the last postseason.
        Ex: 2000.
        """

        # test for valid date.
        testdate = self._validate(optyear, '%Y')
        if not testdate:
            irc.reply("ERROR: Invalid year. Must be YYYY.")
            return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi93b3JsZHNlcmllcy9oaXN0b3J5L3dpbm5lcnM=')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        rows = soup.findAll('tr', attrs={'class': re.compile('^evenrow|^oddrow')})
        # dict for output container. key=year.
        worldseries = collections.defaultdict(list)
        # each year is a worldseries.
        for row in rows:
            tds = row.findAll('td')
            year = tds[0]
            winner = tds[1].getText()
            loser = tds[2].getText()
            series = tds[3].getText()
            worldseries[int(year.getText())] = "Winner: {0}  Loser: {1}  Series: {2}".format(\
                self._bold(utils.str.normalizeWhitespace(winner)), utils.str.normalizeWhitespace(loser), series)
        # prepare to output.
        outyear = worldseries.get(optyear)
        if not outyear:  # if we don't have a year..
            irc.reply("ERROR: I could not find MLB World Series information for: {0}".format(optyear))
            return
        else:  # we have the world series.
            irc.reply("{0} World Series :: {1}".format(self._red(optyear), outyear))

    mlbworldseries = wrap(mlbworldseries, [('int')])

    def mlballstargame(self, irc, msg, args, optyear):
        """<YYYY>
        Display results for that year's MLB All-Star Game. Ex: 1996. Earliest year is 1933 and latest is this season.
        """

        # first test year.
        testdate = self._validate(optyear, '%Y')
        if not testdate:
            irc.reply("ERROR: Invalid year. Must be YYYY.")
            return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9hbGxzdGFyZ2FtZS9oaXN0b3J5')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        rows = soup.findAll('tr', attrs={'class': re.compile('^evenrow|^oddrow')})
        # k/v dict container for output. k = year.
        allstargames = collections.defaultdict(list)
        # each row is an allstar game.
        for row in rows:
            tds = [item.getText() for item in row.findAll('td')]
            allstargames[int(tds[0])] = "Score: {0}  Location: {1}({2})  Att: {3}  MVP: {4}  ".format(tds[1], tds[2], tds[3], tds[4], tds[5])
        # prepare to output.
        outyear = allstargames.get(optyear)
        if not outyear:  # nothing in the years.
            irc.reply("ERROR: I could not find MLB All-Star Game information for: {0}".format(optyear))
            return
        else:  # we do have a year/game.
            irc.reply("{0} All-Star Game :: {1}".format(self._red(optyear), outyear))

    mlballstargame = wrap(mlballstargame, [('int')])

    def mlbcyyoung(self, irc, msg, args):
        """
        Display Cy Young prediction list. Uses a method, based on past results, to predict Cy Young balloting.
        """

        # build and fetch URL.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9mZWF0dXJlcy9jeXlvdW5n')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # now process HTML.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        players = soup.findAll('tr', attrs={'class': re.compile('(^oddrow.*?|^evenrow.*?)')})
        # k/v container for output. key = league (al/nl), values = players.
        cyyoung = collections.defaultdict(list)
        # process each row(player).
        for player in players:
            colhead = player.findPrevious('tr', attrs={'class': 'stathead'})
            tds = [item.getText() for item in player.findAll('td')]
            appendString = "{0}. {1}".format(tds[0], tds[1], tds[2])
            cyyoung[str(colhead.getText())].append(appendString)  # now append.
        # output time.
        for i, x in cyyoung.iteritems():
            irc.reply("{0} :: {1}".format(self._red(i), " | ".join([item for item in x])))

    mlbcyyoung = wrap(mlbcyyoung)

    def mlbarrests(self, irc, msg, args):
        """
        Display the last 5 MLB arrests.
        """

        # build and fetch url.
        url = self._b64decode('aHR0cDovL2FycmVzdG5hdGlvbi5jb20vY2F0ZWdvcnkvcHJvLWJhc2ViYWxsLw==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        #soup = BeautifulSoup(html)
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        ars = soup.findAll('h2', attrs={'class': 'blog-title'})
        if len(ars) == 0:
            irc.reply("No arrests found. Something break?")
            return
        else:
            az = []  # empty list for arrests.
            # iterate over each and inject to list.
            for ar in ars[0:5]:  # iterate over each.
                ard = ar.findNext('div', attrs={'class': 'blog-date'})
                # text and cleanup.
                ard = ard.getText().replace('Posted On', '')
                # print.
                az.append({'d': ard, 'a': ar.getText()})
        # now lets create our output.
        delta = datetime.datetime.strptime(str(az[0]['d']), "%B %d, %Y").date() - datetime.date.today()
        daysSince = abs(delta.days)
        # finally, output.
        irc.reply("{0} days since last arrest :: {1}".format(self._red(daysSince), " | ".join([i['a'] + " " + i['d'] for i in az])))

    mlbarrests = wrap(mlbarrests)

    def mlbroster(self, irc, msg, args, optlist, optteam):
        """[--40man|--active] <team>
        Display active roster for team.
        Defaults to active roster but use --40man switch to show the entire roster.
        Ex: --40man NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # handle optlist (getopts) here.
        active, fortyman = True, False
        for (option, arg) in optlist:
            if option == 'active':
                active, fortyman = True, False
            if option == '40man':
                active, fortyman = False, True
        # conditional url depending on switch above.
        if active and not fortyman:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL3Jvc3Rlci9fL25hbWU=') + '/%s/type/active/' % optteam.lower()
        else:  # 40man
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL3Jvc3Rlci9fL25hbWU=') + '/%s/' % optteam.lower()
        # fetch url.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('div', attrs={'class': 'mod-content'}).find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr', attrs={'class': re.compile('^oddrow player.*|^evenrow player.*')})
        # k/v container for output.
        team_data = collections.defaultdict(list)
        # each row is a player, in a table of position.
        for row in rows:
            playerType = row.findPrevious('tr', attrs={'class': 'stathead'})
            playerNum = row.find('td')
            playerName = playerNum.findNext('td').find('a')
            playerPos = playerName.findNext('td')
            team_data[playerType.getText()].append("{0} ({1})".format(playerName.getText(), playerPos.getText()))
        # output time.
        for i, j in team_data.iteritems():  # output one line per position.
            irc.reply("{0} {1} :: {2}".format(self._red(optteam.upper()), self._bold(i), " | ".join([item for item in j])))

    mlbroster = wrap(mlbroster, [getopts({'active': '', '40man': ''}), ('somethingWithoutSpaces')])

    def _hs(self, s):
        """
        format a size in bytes into a 'human' size.
        """

        try:  # to be safe, wrap in a giant try/except block.
            s = s.replace(',', '').replace('$', '').strip()  # remove $ and ,
            # are we negative?
            if s.startswith('-'):
                negative = True
                s = s.replace('-','')
            else: # not
                negative = False
            # main routine.
            suffixes_table = [('',0),('k',0),('M',1),('B',2),('T',2), ('Z',2)]
            num = float(s)
            for suffix, precision in suffixes_table:
                if num < 1000.0:
                    break
                num /= 1000.0
            # precision.
            if precision == 0:
                formatted_size = "%d" % num
            else:
                formatted_size = str(round(num, ndigits=precision))
            # should we reattach - (neg num)?
            if negative:
                formatted_size = "-" + formatted_size
            # now return.
            return "%s%s" % (formatted_size, suffix)
        except Exception, e:
            self.log.info("_hs: ERROR trying to format: {0} :: {1}".format(s, e))
            return s

    def mlbpayroll(self, irc, msg, args, optteam):
        """<team>
        Display payroll situation for <team>.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # need to translate team for the url
        lookupteam = self._translateTeam('st', 'team', optteam)
        # fetch url.
        url = self._b64decode('aHR0cDovL3d3dy5zcG90cmFjLmNvbS9tbGIv') + '%s/payroll/' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        teamtitle = soup.find('title').getText().split('|')[0].strip()
        # we dont check this below because we want to know when it breaks.
        table = soup.find('table', attrs={'class': 'datatable captotal xs-hide'})
        #irc.reply("{0}".format(table.getText()))
        # quick and dirt, grab the last row.
        rows = table.findAll('tr')[-1:]
        # this row will have 4 TD in them. First is blank, second is base salary, signing bonus, incentives, captotal.
        basesalary = rows[0].findAll('td')[1].getText()
        signingbonus = rows[0].findAll('td')[2].getText()
        incentives = rows[0].findAll('td')[3].getText()
        captotal = rows[0].findAll('td')[4].getText()
        # format them.
        basesalary = self._hs(basesalary)
        signingbonus = self._hs(signingbonus)
        incentives = self._hs(incentives)
        captotal = self._hs(captotal)
        # output
        irc.reply("{0} :: {1} | Base Salaries: {2} | Signing Bonuses: {3} | Incentives: {4}".format(self._bold(teamtitle), captotal, basesalary, signingbonus, incentives))

    mlbpayroll = wrap(mlbpayroll, [('somethingWithoutSpaces')])

    def mlbleaders(self, irc, msg, args, optlist, optleague, optstat):
        """<mlb|nl|al> <statname>

        Display MLB/AL/NL leaders in various stat categories.
        Valid categories: AVG, HR, RBI, R, OBP, SLUGGING, OPS, SB, W, ERA, SO, S, WHIP

        Ex: mlb ops
        """

        # first, we declare our very long list of categories. used for validity/matching/url and the help.
        stats = {
        'AVG': 'avg',
        'HR': 'homeRuns',
        'RBI': 'RBIs',
        'R': 'runs',
        'OBP': 'onBasePct',
        'SLUGGING': 'slugAvg',
        'OPS': 'OPS',
        'SB': 'stolenBases',
        'W': 'wins',
        'ERA': 'ERA',
        'SO': 'strikeouts',
        'S': 'saves',
        'WHIP': 'WHIP'
        }
        # handle league. check for valid.
        optleague = optleague.upper()  # upper to match.
        # validate the leagues.
        validleagues = {'MLB': '9', 'NL': '8', 'AL': '7'}
        if optleague not in validleagues:  # invalid league found.
            irc.reply("ERROR: '{0}' is an invalid league. Must specify {1}".format(optleague, " | ".join(validleagues.keys())))
            return
        # validate the category.
        optstat = optstat.upper()  # lower to match.
        if optstat not in stats:
            irc.reply("ERROR: '{0}' is an invalid category. Must be one of: {1}".format(optstat, " | ".join(stats.keys())))
            return
        # now we build URL.
        url = b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL2xlYWd1ZWxlYWRlcnM=')
        url += '?' + 'category=%s&groupId=%s&fa6hno2nn2px0=GO&y=1&wjb=' % (stats[optstat], validleagues[optleague])
        # now, with the url, fetch and return content.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity check before we can process html.
        if 'No results available based on the selected criteria.' in html:
            irc.reply("ERROR: No results available based on the selected criteria. If using a year, make sure that season has been played.")
            return
        # process HTML.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('table', attrs={'class': 'table', 'width': '100%', 'cellspacing': '0'})  # table class="table" width="100%" cellspacing="0"
        trs = table.findAll('tr')[1:]  # skip the header row.
        # lets do a sanity check.
        if len(trs) == 0:
            irc.reply("ERROR: No stats found. Too early in the year?")
            return
        # we're good. container for the output.
        mlbstats = []
        # process the rows
        for tr in trs:
            tds = tr.findAll('td')
            rk = tds[0].getText()
            plr = tds[1].getText().encode('utf-8')
            st = tds[2].getText()
            mlbstats.append("{0}. {1} ({2})".format(rk, plr, st))
        # now we prepare the output.
        irc.reply("MLB LEADERS IN {0}({1}) :: {2}".format(self._ul(optstat), self._bold(optleague), " | ".join(mlbstats)))

    mlbleaders = wrap(mlbleaders, [getopts({'postseason': '', 'bottom': ''}), ('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbcareerleaders(self, irc, msg, args, optplayertype, optcategory):
        """<batting|pitching> <category>
        Display career stat leaders in batting|pitching <category>
        Must specify batting or pitching, along with stat from either category.
        Ex: batting batavg OR pitching wins
        """

        battingcategories = { 'batavg':'batting_avg', 'onbasepct':'onbase_perc', 'sluggingpct':'slugging_perc' ,
                            'onbaseplusslugging':'onbase_plus_slugging', 'gamesplayedAB':'G', 'atbats':'AB', 'plateappear':'PA',
                            'runsscored':'R', 'hitsAB':'H', 'totalbases':'TB', 'doubles':'2B', 'triples':'3B', 'homeruns':'HR',
                            'runsbattedin':'RBI', 'basesonballs':'BB', 'strikeouts':'SO', 'singles':'1B', 'runscreated':'RC',
                            'timesonbase':'TOB', 'offwinpct':'offensive_winning_perc', 'hitbypitchAB':'HBP', 'sachits':'SH', 'sacflies':'SF',
                            'intbasesonballs':'IBB', 'dpgroundedinto':'GIDP', 'caughtstealing':'CS','SBpct':'stolen_base_perc',
                            'powerspeednum':'power_speed_number', 'ABperSO':'at_bats_per_strikeout', 'ABperHR':'at_bats_per_home_run',
                            'outsmade':'outs_made'
                            }
        pitchingcategories = { 'warforpitchers':'WAR_pitch', 'ERA':'earned_run_avg', 'wins':'W', 'winlosspct':'win_loss_perc',
                            'walksnhitsperIP':'whip', 'hitsper9IP':'hits_per_nine', 'bobper9IP':'bases_on_balls_per_nine',
                            'SOper9IP':'strikeouts_per_nine', 'gamesplayedpitching':'G_p', 'saves':'SV', 'inningspitched':'IP',
                            'strikeouts':'SO_p', 'gamesstarted':'GS', 'completegames':'CG', 'shutouts':'SHO', 'homerunsallowed':'HR_p',
                            'baseonballsallowed':'BP_p', 'hitsallowed':'H_p', 'SOnBOB':'strikeouts_per_base_on_balls', 'HRper9IP':'home_runs_per_nine',
                            'losses':'L', 'earnedruns':'ER', 'wildpitches':'WP', 'hitbypitch':'HBP_p', 'battersfaced':'batters_faced',
                            'gamesfinished':'GF', 'adjustedERAplus':'earned_run_avg_plus', 'adjpitchingruns':'apRuns', 'adjpitchingwins':'apWins'
                            }

        # have to match a k/v in each dict with batting or pitching.
        optplayertype = optplayertype.lower()  # first lower optplayertype
        if optplayertype == "batting":  # check if issued batting w/o a category.
            if not optcategory:  # no category.
                irc.reply("Valid batting categories: {0}".format(" | ".join(sorted(battingcategories.keys()))))
                return
            else:  # we have a category.
                #optcategory = optcategory.lower()
                if optcategory not in battingcategories:  # invalid category.
                    irc.reply("ERROR: Batting stat must be one of: {0}".format(" | ".join(sorted(battingcategories.keys()))))
                    return
                else:  # we have a valid category so pass.
                    endurl = '%s_career.shtml' % battingcategories[optcategory]
        elif optplayertype == "pitching":  # check pitching.
            if not optcategory:  # we got pitching but no category.
                irc.reply("Valid pitching categories: {0}".format(" | ".join(sorted(pitchingcategories.keys()))))
                return
            else:  # we got pitching and a category.
                #optcategory = optcategory.lower()
                if optcategory not in pitchingcategories:  # but category was invalid.
                    irc.reply("ERROR: Pitching stat pitching categories: {0}".format(" | ".join(sorted(pitchingcategories.keys()))))
                    return
                else:  # pitching category was valid.
                    endurl = '%s_career.shtml' % pitchingcategories[optcategory]
        else:  # batting or pitching was not specified.
            irc.reply("ERROR: Must specify batting or pitching.")
            return
        # now that we're done validating the category and have our endurl, build and fetch url.
        url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2xlYWRlcnMv') + endurl
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # parse html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        #soup = BeautifulSoup(html.replace('&nbsp;',' '))
        table = soup.find('table', attrs={'data-crop': '50'})
        rows = table.findAll('tr')[1:11]  # skip first row (header) and get the next 10.
        # output container is a list.
        object_list = []
        # each row is a player.
        for row in rows:
            rank = row.find('td', attrs={'align': 'right'})
            player = rank.findNext('td')
            stat = player.findNext('td')
            if player.find('strong'):  # ul players are active.
                player = self._ul(player.find('a').find('strong').getText().strip())
            else:  # inactive (+ = HOF).
                player = player.find('a').getText()
            object_list.append("{0} {1} ({2})".format(rank.getText(), self._bold(player.encode('utf-8')), stat.getText()))
        # output time. output header row then our objects.
        output = "{0} {1} (+ indicates HOF; {2} indicates active.)".format(self._red("MLB Career Leaders for: "),\
            self._bold(optcategory), self._ul("UNDERLINE"))
        irc.reply(output)  # header.
        irc.reply(" | ".join([item for item in object_list]))  # now our top10.

    mlbcareerleaders = wrap(mlbcareerleaders, [('somethingWithoutSpaces'), optional('somethingWithoutSpaces')])

    def mlbawards(self, irc, msg, args, optyear):
        """<year>
        Display various MLB award winners for current (or previous) year. Use YYYY for year.
        Ex: 2011
        """

        # test if we have date or not.
        if optyear:   # crude way to find the latest awards.
            testdate = self._validate(optyear, '%Y')
            if not testdate:
                irc.reply("Invalid year. Must be YYYY.")
                return
        else:  # we don't have a year, so find the latest.
            url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2F3YXJkcy8=')
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
            soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
            # parse page. find summary. find the first link text. this is our year.
            link = soup.find('big', text="Baseball Award Voting Summaries").findNext('a')['href'].strip()
            optyear = ''.join(i for i in link if i.isdigit())
        # fetch actual awards page .
        url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2F3YXJkcy8=') + 'awards_%s.shtml' % optyear
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # check if we have the page like if we're not done the 2013 season and someone asks for 2013.
        if "404 - File Not Found" in html:
            irc.reply("ERROR: I found no award summary for: {0}".format(optyear))
            return
        # create our variables based on soup.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        alvp = soup.find('h2', text="AL MVP Voting").findNext('table', attrs={'id': 'AL_MVP_voting'}).findNext('a').text
        nlvp = soup.find('h2', text="NL MVP Voting").findNext('table', attrs={'id': 'NL_MVP_voting'}).findNext('a').text
        alcy = soup.find('h2', text="AL Cy Young Voting").findNext('table', attrs={'id': 'AL_Cy_Young_voting'}).findNext('a').text
        nlcy = soup.find('h2', text="NL Cy Young Voting").findNext('table', attrs={'id': 'NL_Cy_Young_voting'}).findNext('a').text
        alroy = soup.find('h2', text="AL Rookie of the Year Voting").findNext('table', attrs={'id': 'AL_Rookie_of_the_Year_voting'}).findNext('a').text
        nlroy = soup.find('h2', text="NL Rookie of the Year Voting").findNext('table', attrs={'id': 'NL_Rookie_of_the_Year_voting'}).findNext('a').text
        almgr = soup.find('h2', text="AL Mgr of the Year Voting").findNext('table', attrs={'id': 'AL_Mgr_of_the_Year_voting'}).findNext('a').text
        nlmgr = soup.find('h2', text="NL Mgr of the Year Voting").findNext('table', attrs={'id': 'NL_Mgr_of_the_Year_voting'}).findNext('a').text
        # prepare output string.
        output = "{0} MLB Awards :: MVP: AL {1} NL {2}  CY: AL {3} NL {4}  ROY: AL {5} NL {6}  MGR: AL {7} NL {8}".format( \
            self._red(optyear), self._bold(alvp), self._bold(nlvp), self._bold(alcy), self._bold(nlcy),\
            self._bold(alroy), self._bold(nlroy), self._bold(almgr), self._bold(nlmgr))
        # actually output.
        irc.reply(output)

    mlbawards = wrap(mlbawards, [optional('int')])

    def mlbschedule(self, irc, msg, args, optteam):
        """<team>
        Display the next five upcoming games for team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # translate team for url.
        lookupteam = self._translateTeam('eshort', 'team', optteam)  # (db, column, optteam)
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL3NjaGVkdWxlL18vbmFtZQ==') + '/%s/' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # now soup the actual html. BS cleans up the RSS because the HTML is junk.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        div = soup.find('div', attrs={'id': 'my-teams-table'})
        table = div.find('table', attrs={'class': 'tablehead'})
        trs = table.findAll('tr', attrs={'class': re.compile('^evenrow.*|^oddrow.*')})
        #
        container = []
        #
        for (i, tr) in enumerate(trs):
            tds = tr.findAll('td')
            if len(tds) == 7 or len(tds) == 8:
                sta = tds[3].getText()
                if sta == "" or sta == "MLB Network":
                    container.append(i)
        #
        if len(container) > 0:
            schednum = container[0]
        else:
            self.log.info("ERROR: mlbschedule. I only got {0} in container (no [2])".format(container))
            irc.reply("ERROR: Something went wrong looking up the schedule. Try again later.")
            return
        #
        schedule = []
        #
        for tr in trs[schednum:schednum+5]:
            tds = tr.findAll('td')
            dte = tds[0].getText().encode('utf-8')
            opp = tds[1].getText().encode('utf-8').replace('vs', 'vs ')
            sta = tds[2].getText().encode('utf-8')
            schedule.append("{0} {1} {2}".format(dte, opp, sta))
        # prepare output string and output.
        descstring = " | ".join([item for item in schedule])
        irc.reply("{0} :: {1}".format(self._bold(optteam), descstring))

    mlbschedule = wrap(mlbschedule, [('somethingWithoutSpaces')])

    def mlbdailyleaders(self, irc, msg, args):
        """
        Display MLB daily leaders.
        """

        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy9kYWlseWxlYWRlcnM=')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity check.
        if "Daily leaders not available" in html:
            irc.reply("Sorry, mlbdailyleaders is not available right now")
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        mlbdate = soup.find('h1', attrs={'class': 'h2'})
        div = soup.find('div', attrs={'id': 'my-players-table'})
        if not div:
            irc.reply("ERROR: Broken HTML. Check page formatting.")
            return
        table = div.find('table', attrs={'class': 'tablehead', 'cellpadding': '3', 'cellspacing': '1'})
        if not table:
            irc.reply("ERROR: Broken HTML. Check page formatting.")
            return
        rows = table.findAll('tr', attrs={'class': re.compile('evenrow.*|oddrow.*')})
        # container
        mlbdailyleaders = []
        # iterate over each row.
        for (i, row) in enumerate(rows[0:10]):
            tds = row.findAll('td')
            plr = tds[1].getText().encode('utf-8')
            mlbdailyleaders.append("{0}. {1}".format(i+1, plr))
        # now output.
        irc.reply("{0} :: {1}".format(self._bold(mlbdate.getText()), " ".join([i for i in mlbdailyleaders])))

    mlbdailyleaders = wrap(mlbdailyleaders)

    def mlbwildcard(self, irc, msg, args):
        """
        Display AL/NL Wildcard standings.
        """

        url = 'http://m.mlb.com/standings/?view=wildcard'
        # now fetch url.
        page = requests.get(url)
        if not page:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        tree = html.fromstring(page.content)
        alwct = tree.xpath('//*[@id="league-103"]/table[2]//span[@class="title-short"]/text()')
        alwcg = tree.xpath('//*[@id="league-103"]/table[2]//td[@class="standings-col-gb"]/text()')
        nlwct = tree.xpath('//*[@id="league-104"]/table[2]//span[@class="title-short"]/text()')
        nlwcg = tree.xpath('//*[@id="league-104"]/table[2]//td[@class="standings-col-gb"]/text()')
        out = collections.defaultdict(list)
        for idx, val in enumerate(alwct):
            if idx > 0:
                out["ALWC"].append("{0} -{1}".format(self._bold(val), alwcg[idx]))
            else:
                out["ALWC"].append("{0} {1}".format(self._bold(val), alwcg[idx]))
        for idx, val in enumerate(nlwct):
            if idx > 0:
                out["NLWC"].append("{0} -{1}".format(self._bold(val), nlwcg[idx]))
            else:
                out["NLWC"].append("{0} {1}".format(self._bold(val), nlwcg[idx]))
        #
        for (z, x) in list(out.items()):
            irc.reply("{0} :: {1}".format(self._bold(z), ", ".join([a for a in x])))

    mlbwildcard = wrap(mlbwildcard)

    def mlbstandings(self, irc, msg, args, optdiv):
        """<ALE|ALC|ALW|NLE|NLC|NLW>

        Display division standings.
        """

        optdiv = optdiv.upper()  # upper to match keys. values are in the table to match with the html.
        leaguetable = {'ALE': '//*[@id="league-103"]/table[1]',
                       'ALC': '//*[@id="league-103"]/table[2]',
                       'ALW': '//*[@id="league-103"]/table[3]',
                       'NLE': '//*[@id="league-104"]/table[1]',
                       'NLC': '//*[@id="league-104"]/table[2]',
                       'NLW': '//*[@id="league-104"]/table[3]'}
        if optdiv not in leaguetable:  # make sure keys are present.
            irc.reply("ERROR: League must be one of: {0}".format(" | ".join(sorted(leaguetable.keys()))))
            return

        # build and fetch url. diff urls depending on option.
        url = 'http://m.mlb.com/standings/'
        # now fetch url.
        page = requests.get(url)
        if not page:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        tree = html.fromstring(page.content)
        teams = tree.xpath('{0}//span[@class="title-short"]/text()'.format(leaguetable[optdiv]))
        gb = tree.xpath('{0}//td[@class="standings-col-gb"]/text()'.format(leaguetable[optdiv]))
        out = []
        for idx, val in enumerate(teams):
            out.append("{0} -{1}".format(val, gb[idx]))
        # output to irc.
        irc.reply("{0} :: {1}".format(optdiv, ", ".join([i for i in out])))

    mlbstandings = wrap(mlbstandings, [('somethingWithoutSpaces')])

    def mlblineup(self, irc, msg, args, optteam):
        """<team>
        Gets lineup for MLB team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # create url and fetch lineup page.
        url = self._b64decode('aHR0cDovL2Jhc2ViYWxscHJlc3MuY29tL2xpbmV1cF90ZWFtLnBocD90ZWFtPQ==') + optteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity check.
        if 'No game today' in html:
            irc.reply("ERROR: No game today for {0}".format(optteam))
            return
        # process html. this is kinda icky.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        div = soup.find('div', attrs={'class': 'team-lineup highlight'})
        # test if we have a game?
        if "No game" in div.getText():
            irc.reply("Sorry, I don't have a game for today.")
            return
        divs = div.findAll('div')
        # 20140330 - had to fix this again.
        gmdate = divs[1].getText()  # date of game.
        seconddiv = divs[3]   # opp pitcher.
        otherpitcher = seconddiv.getText()  # opp pitcher and team.
        lineup = div.find('div', attrs={'class': 'game-lineup'})
        # sanity check.
        if "No lineup yet" in lineup.getText():
            irc.reply("Sorry, I don't have a lineup yet for: {0}".format(gmdate))
            return
        else:  # div is a collection of divs, each div = person in lineup.
            lineup = lineup.findAll('div')
            lineup = " | ".join([i.getText(separator=' ').encode('utf-8') for i in lineup])
        # output.
        irc.reply("{0} LINEUP :: ({1}, {2}) :: {3}".format(self._bold(optteam), gmdate, otherpitcher, lineup))

    mlblineup = wrap(mlblineup, [('somethingWithoutSpaces')])

    def mlbinjury(self, irc, msg, args, optlist, optteam):
        """[--details] <team>
        Show all injuries for team.
        Use --details to display full table with team injuries.
        Ex: --details BOS or NYY
        """

        # handle optlist (getopts)
        details = False
        for (option, arg) in optlist:
            if option == 'details':
                details = True
        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build and fetch url.
        lookupteam = self._translateTeam('roto', 'team', optteam)
        url = self._b64decode('aHR0cDovL3JvdG93b3JsZC5jb20vdGVhbXMvaW5qdXJpZXMvbWxi') + '/%s/' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        if not soup.find('div', attrs={'class': 'player'}):
            irc.reply("No injuries found for: {0}".format(optteam))
            return
        # if we do, find the table.
        table = soup.find('table', attrs={'align': 'center', 'width': '600px;'})
        rows = table.findAll('tr')[1:]
        # output list.
        object_list = []
        # first is header, rest is injury.
        for row in rows:
            tds = row.findAll('td')
            d = {}
            d['name'] = tds[0].find('a').getText().encode('utf-8')
            d['status'] = tds[3].getText().encode('utf-8')
            d['date'] = tds[4].getText().strip().replace("&nbsp;", " ").encode('utf-8')
            d['injury'] = tds[5].getText().encode('utf-8')
            d['returns'] = tds[6].getText().encode('utf-8')
            object_list.append(d)  # append the dict in the list.
        # are there any injuries?
        if len(object_list) < 1:
            irc.reply("{0} :: No injuries.".format(self._red(optteam)))
            return
        # output time. conditional if we're showing details or not.
        if details:  # show each injury with details.
            irc.reply("{0} :: {1} Injuries".format(self._red(optteam), len(object_list)))
            irc.reply("{0:27} {1:9} {2:<10} {3:<15} {4:<15}".format("NAME", "STATUS", "DATE", "INJURY", "RETURNS"))
            for inj in object_list:  # one per line since we are detailed.
                irc.reply("{0:<27} {1:<9} {2:<10} {3:<15} {4:<15}".format(inj['name'], inj['status'], inj['date'], inj['injury'], inj['returns']))
        else:  # no detail.
            irc.reply("{0} :: {1} Injuries".format(self._red(optteam), len(object_list)))
            irc.reply(" | ".join([item['name'] + " (" + item['returns'] + ")" for item in object_list]))

    mlbinjury = wrap(mlbinjury, [getopts({'details': ''}), ('somethingWithoutSpaces')])

    def mlbleagueleaders(self, irc, msg, args, optleague, optcategory):
        """<MLB|AL|NL> <category>
        Display top 10 teams in category for a specific stat.
        Categories: hr, avg, rbi, ra, sb, era, whip, k
        Ex: MLB hr or AL rbi or NL era
        """

        # establish valid leagues and valid categories.
        league = {'mlb': '9', 'al': '7', 'nl': '8'}  # do our own translation here for league/category.
        category = {'avg': 'avg', 'hr': 'homeRuns', 'rbi': 'RBIs', 'ra': 'runs', 'sb': 'stolenBases', 'era': 'ERA', 'whip': 'whip', 'k': 'strikeoutsPerNineInnings'}
        # check if we have valid league/category.
        optleague, optcategory = optleague.lower(), optcategory.lower()
        if optleague not in league:  # invalid league.
            irc.reply("ERROR: League must be one of: {0}".format(" | ".join(sorted(league.keys()))))
            return
        if optcategory not in category:  # invalid category.
            irc.reply("ERROR: Category must be one of: {0}".format(" | ".join(sorted(category.keys()))))
            return
        # build and fetch url. it's conditional based on k/v above.
        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL2FnZ3JlZ2F0ZXM=')
        url += '?category=%s&groupId=%s&y=1&wjb=' % (category[optcategory], league[optleague])
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('table', attrs={'class': 'table'})
        rows = table.findAll('tr')
        # list for output.
        append_list = []
        # one per row. first row = header. top 5 only.
        for row in rows[1:11]:
            tds = row.findAll('td')
            rank = tds[0].getText()
            team = tds[1].getText()
            num = tds[2].getText()
            append_list.append("{0}. {1} {2}".format(rank, team, num))
        # output
        thelist = " | ".join([item for item in append_list])
        irc.reply("Leaders in {0} for {1} :: {2}".format(self._red(optleague.upper()), self._bold(optcategory.upper()), thelist))

    mlbleagueleaders = wrap(mlbleagueleaders, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbprob(self, irc, msg, args, optteam):
        """<TEAM>
        Display the MLB probables for a team over the next 5 starts.
        Ex: NYY.
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # put today + next 4 dates in a list, YYYYmmDD via strftime
        dates = [(datetime.date.today() + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(5)]
        # output container for each day/start.
        probables = []
        # now iterate through each day.
        for eachdate in dates:
            # build and fetch url.
            url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3Byb2JhYmxlcz93amI9') + '&date=%s' % eachdate
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
            # process html. must do a sanity check + mangle team names before anything.
            # if no games on, NEXT. (like around the ASB)
            if "No Games Scheduled" in html:
                next
            # have to mangle these because of horrid abbreviations.
            html = html.replace('WAS', 'WSH').replace('CHW', 'CWS').replace('KAN', 'KC').replace('TAM', 'TB').replace('SFO', 'SF').replace('SDG', 'SD')
            # process html.
            soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
            rows = soup.findAll('div', attrs={'class': re.compile('ind alt tL spaced|ind tL spaced')})
            # each row is a game that day.
            for row in rows:  # we grab the matchup (text) to match. the rest goes into a dict.
                textmatch = re.search(r'<a class="bold inline".*?<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)$', row.renderContents(), re.I|re.S|re.M)
                if textmatch:  # only inject if we match
                    d = {}
                    d['date'] = eachdate  # text from above. use BS for matchup and regex for the rest.
                    d['matchup'] = row.find('a', attrs={'class': 'bold inline'}).getText().strip()
                    d['vteam'] = textmatch.group(1).strip().replace(':', '')
                    d['vpitcher'] = textmatch.group(2).strip()
                    d['vpstats'] = textmatch.group(3).strip()
                    d['hteam'] = textmatch.group(4).strip().replace(':', '')
                    d['hpitcher'] = textmatch.group(5).strip()
                    d['hpstats'] = textmatch.group(6).strip()
                    probables.append(d)  # order preserved via list. we add the dict.
        # check to see if we have anything?
        if len(probables) == 0:
            irc.reply("Sorry, I have no probables for {0}".format(optteam))
            return
        # now lets output.
        for eachentry in probables:  # iterate through list and only output when team is matched.
            if optteam in eachentry['matchup']:  # if optteam is contained in matchup, we output.
                irc.reply("{0:10} {1:25} {2:4} {3:15} {4:15} {5:4} {6:15} {7:15}".format(eachentry['date'], eachentry['matchup'],\
                    eachentry['vteam'], eachentry['vpitcher'],eachentry['vpstats'], eachentry['hteam'], eachentry['hpitcher'], eachentry['hpstats']))

    mlbprob = wrap(mlbprob, [('somethingWithoutSpaces')])

    #############################
    # PLAYER FIND / STATS STUFF #
    #############################

    def _sanitizeName(self, name):
        """ Sanitize name. """

        name = name.lower()  # lower.
        name = name.strip('.')  # remove periods.
        name = name.strip('-')  # remove dashes.
        name = name.strip("'")  # remove apostrophies.
        # possibly strip jr/sr/III suffixes in here?
        return name

    def _similarPlayers(self, optname):
        """Return a dict containing the five most similar players based on optname."""

        url = self._b64decode('aHR0cHM6Ly9lcmlrYmVyZy5jb20vbWxiL3BsYXllcnM=')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.info("ERROR opening {0}".format(url))
            return None
        # now that we have the list, lets parse the json.
        try:
            soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
            table = soup.find('table')
            # do a sanity check.
            trs = table.find('tbody').findAll('tr')
            activeplayers = []
            # iterate over each row.
            for tr in trs:
                tds = tr.findAll('td')
                i = tds[0].getText().replace('.', '')  # id.
                n = tds[1].find('a').getText() #.encode('utf-8')  # name.
                #n = ftfy.fix_text(n)
                activeplayers.append({'id': i, 'full_name': n})
        except Exception, e:
            self.log.info("ERROR: _similarPlayers :: Could not parse source for players :: {0}".format(e))
            return None
        # test length as sanity check.
        if len(activeplayers) == 0:
            self.log.info("ERROR: _similarPlayers :: length 0. Could not find any players in players source")
            return None
        # ok, finally, lets go.
        optname = self._sanitizeName(optname)  # sanitizename.
        optname = unicode(optname)  # must be unicode.
        jaro, damerau = [], []  # empty lists to put our results in.
        # now we create the container to iterate over.
        names = [{'fullname': self._sanitizeName(v['full_name']), 'id':v['id']} for v in activeplayers]  # full_name # last_name # first_name
        # iterate over the entries.
        for row in names:  # list of dicts.
            try:  # some error stuff.
                jaroscore = jellyfish.jaro_distance(optname, row['fullname'])  # jaro.
                damerauscore = jellyfish.damerau_levenshtein_distance(optname, row['fullname'])  # dld
                jaro.append({'jaro': jaroscore, 'fullname': row['fullname'], 'id': row['id']})  # add dict to list.
                damerau.append({'damerau': damerauscore, 'fullname': row['fullname'], 'id': row['id']})  # ibid.
            except Exception as e:
                self.log.info("_similarPlayers :: ERROR :: {0} :: {1}".format(row, e))
                continue
        # now, we do two "sorts" to find the "top5" matches. reverse is opposite on each.
        jarolist = sorted(jaro, key=itemgetter('jaro'), reverse=True)[0:5]  # bot five.
        dameraulist = sorted(damerau, key=itemgetter('damerau'), reverse=False)[0:5]  # top five.
        # we now have two lists, top5 sorted, and need to do some further things.
        # now, lets iterate through both lists. match if both are in it. (better matches)
        matching = [k for k in jarolist if k['id'] in [f['id'] for f in dameraulist]]
        # now, test if we have anything. better matches will have more.
        if len(matching) == 0:  # we have NO matches. grab the top two from jaro/damerau (for error str)
            matching = [jarolist[0], dameraulist[0], jarolist[1], dameraulist[1]]
            self.log.info("_similarPlayers :: NO MATCHES for {0} :: {1}".format(optname, matching))
        # return matching now.
        return matching

    def _pf(self, db, pname):
        """<e|r|s> <player>

        Find a player's page via google ajax. Specify DB based on site.
        """

        # sanitize.
        pname = self._sanitizeName(pname)

        # db.
        if db == "e":  # espn.
            burl = "site:espn.go.com/mlb/player/ %s" % pname
        elif db == "r":  # rworld.
            burl = "site:www.rotoworld.com/player/mlb/ %s" % pname
        elif db == "s":  # st.
            burl = "site:www.spotrac.com/mlb/ %s" % pname
        elif db == "br":  # br.
            burl = "site:www.baseball-reference.com/minors/ %s" % pname

        # urlencode.
        try:
            burl = quote_plus("'" + burl + "'")
            url = self._b64decode("aHR0cHM6Ly93d3cuZ29vZ2xlLmNvbS8=") + "search?q=%s&ie=utf-8&oe=utf-8&aq=t&rls=org.mozilla:en-US:official&client=firefox-a&channel=sb" % (burl)
            headers = {'User-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0'}
            r = requests.get(url, headers=headers)
            html = BeautifulSoup(r.content)
            div = html.find('div', attrs={'id': 'search'})
            lnks = div.findAll('a')
            if len(lnks) == 0:
                return None
            lnkone = lnks[0]
            return lnkone['href']
        except Exception as e:
            self.log.info("ERROR :: _pf :: {0}".format(e))
            return None

    def _so(self, d):
        """<dict>

        Input dict of stats. Order them properly.
        """

        so = ['GP', 'AB', 'AVG', 'HR', 'RBI', 'SB', 'CS', 'R', 'H', '2B', '3B', 'OBP', 'SLG', 'OPS', 'BB', 'SO',
              'IP', 'W', 'L', 'SV', 'ERA', 'WHIP', 'BB', 'SO', 'H', 'HR', 'HLD', 'BLSV', 'R', 'CG', 'SHO', 'WAR']
        # one liner is always better.
        o = [self._bold(v) + ": " + d[v] for v in so if v in d]
        # we return the list.
        return o

    def milbplayerseason(self, irc, msg, args, optyear, optplayer):
        """<YYYY> <player name>

        Display season stats, for season (YYYY), by player.
        Ex: 2010 Mike Trout
        """

        # try and grab a player.
        url = self._pf('br', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        div = soup.find('div', attrs={'class': 'table_container'})
        if not div:
            irc.reply("ERROR: No player information for '{0}' at '{1}'".format(optplayer, url))
            return
        table = div.find('table')
        if not table:
            irc.reply("ERROR: No player information for '{0}' at '{1}'".format(optplayer, url))
            return
        # playername:
        pn = soup.find('span', attrs={'id': 'player_name'}).getText().encode('utf-8')
        # columns. bad parsing on BS end. We don't know what comes back. lets do a neat trick here.
        chz = table.find('thead').findAll('th')
        ch = []
        for i in chz:  # iterate over all.
            ds = i['data-stat'].encode('utf-8')
            dst = i.getText().encode('utf-8')
            if len(ds) > len(dst):  # see what is longer.
                ch.append(dst)
            else:  # cheap but works.
                ch.append(ds)
        # now each row.
        rows = table.find('tbody').findAll('tr')
        # our container
        y = collections.defaultdict(list)
        for row in rows:
            tds = row.findAll('td')
            # first should be year.
            yr = int(tds[0].getText().encode('utf-8'))
            # output.
            rest = []
            # rest of the text lets join it up. we iterate over each so we can cherrypick.
            for (i, x) in enumerate(tds[1:]):
                xch = ch[i+1]
                xt = x.getText().encode('utf-8')
                if xch == "age_diff":
                    continue
                rest.append("{0}: {1}".format(xch, xt))
            # add into the dd.
            y[yr].append(rest)
        # try this on the output.
        out = y.get(optyear)
        if not out:  # we did NOT find year in their stats.
            irc.reply("ERROR: I did not find {0} stats for {1}. I do have for: {2}".format(optyear, pn, " | ".join([str(z) for z in y.keys()])))
            return
        # we never know how many stops so lets just for loop it. can get floody/spammy.
        for q in out:
            irc.reply("{0} :: {1} :: {2}".format(self._red(pn), self._bold(optyear), " ".join(q)))

    milbplayerseason = wrap(milbplayerseason, [('int'), ('text')])

    def milbplayerinfo(self, irc, msg, args, optplayer):
        """<player name>

        Display minor league information about player.
        Ex: Mike Trout
        """

        # try and grab a player.
        url = self._pf('br', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        div = soup.find('div', attrs={'itemtype': 'http://data-vocabulary.org/Person'})
        if not div:
            irc.reply("ERROR: No player information for '{0}' at '{1}'".format(optplayer, url))
            return
        # now grab their name.
        n = div.find('span', attrs={'id': 'player_name'})
        pn = n.getText().encode('utf-8')
        n.extract()
        # remove ads/js.
        #[a.extract() for a in div.find('div', attrs={'class':'sr_draftstreet '})]
        [s.extract() for s in div('script')]
        # remove comments.
        comments = div.findAll(text=lambda text: isinstance(text, Comment))
        [comment.extract() for comment in comments]
        # text.
        t = div.getText(separator=' ').encode('utf-8')
        t = ' '.join(t.split())  # n+1 space = one
        # remove ads?
        t = t.replace("Support us without the ads? Go Ad-Free.", "")
        # format for output.
        irc.reply("{0} :: {1}".format(self._bold(pn), t))

    milbplayerinfo = wrap(milbplayerinfo, [('text')])

    def mlbplayercontract(self, irc, msg, args, optplayer):
        """<player name>

        Display known contract details for active player.
        Ex: Derek Jeter.
        """

        # try and grab a player.
        url = self._pf('r', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        plrname = soup.find('div', attrs={'class': 'playername'})
        if not plrname:
            irc.reply("ERROR: I could not find player's name on: {0}".format(url))
            return
        else:  # grab their name and stuff.
            plrname = plrname.find('h1').getText().encode('utf-8')
            plrname = plrname.split('|', 1)[0].strip()  # split at | to strip pos. remove double space.
        # now find the n00z.
        div = soup.find('div', attrs={'class': 'report'})
        if not div:
            irc.reply("ERROR: I could not find player contract for: {0} at {1}".format(optplayer, url))
            return
        # race condition here discovered by someone:
        parentdiv = div.findParent('div')
        if parentdiv['class'] == "playercard":
            irc.reply("{0} :: {1}".format(self._bold(plrname), div.getText().encode('utf-8')))
        else:
            irc.reply("{0} :: I'm sorry but no contract details are listed on: {1}".format(self._bold(plrname), url))

    mlbplayercontract = wrap(mlbplayercontract, [('text')])

    def mlbplayernews(self, irc, msg, args, optplayer):
        """<player name>

        Display latest news for player via Rotoworld.
        Ex: Derek Jeter.
        """

        # try and grab a player.
        url = self._pf('r', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        plrname = soup.find('div', attrs={'class': 'playername'})
        if not plrname:
            irc.reply("ERROR: I could not find player's name on: {0}".format(url))
            return
        else:  # grab their name and stuff.
            plrname = plrname.find('h1').getText().encode('utf-8')
            plrname = plrname.split('|', 1)[0].strip()  # split at | to strip pos. remove double space.
        # now find the n00z.
        div = soup.find('div', attrs={'class': 'playernews'})
        if not div:
            irc.reply("ERROR: I could not find player news for: {0} at {1}".format(optplayer, url))
            return
        # we do have stuff. output.
        playerNews = div.getText().encode('utf-8')
        # remove html tags before.
        TAG_RE = re.compile(r'<[^>]+>')
        playerNews = TAG_RE.sub('', playerNews)
        # output.
        irc.reply("{0} :: {1}".format(self._bold(plrname), playerNews))

    mlbplayernews = wrap(mlbplayernews, [('text')])

    def mlbcareerstats(self, irc, msg, args, optplayer):
        """<player name>

        Display career totals and season averages for player.
        Ex: Don Mattingly or Rickey Henderson or Derek Jeter.
        """

        # try and grab a player.
        url = self._pf('e', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # mangle url
        url = url.replace('/mlb/player/_/id/', '/mlb/player/stats/_/id/')
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        plrname = soup.findAll('h1')[0].getText().encode('utf-8')
        table = soup.find('table', attrs={'class': 'tablehead', 'cellspacing': '1', 'cellpadding': '3'})
        if not table:  # sanity check.
            irc.reply("ERROR: Something went wrong looking up career stats for: {0}. Check formatting.".format(optplayer))
            return
        colhead = table.find('tr', attrs={'class': 'colhead'}).findAll('td')
        trs = table.findAll('tr', attrs={'class': re.compile('oddrow bi|evenrow bi')})
        #
        if len(trs) != 2:
            irc.reply("ERROR: Something went wrong looking up career stats for: {0}. Check formatting.".format(optplayer))
            return
        # first row has two 2ds. lets list cmp this with some nifty one liner!.
        #careertotals = [self._bold(colhead[i+2].getText()) + ": " + z.getText() for (i, z) in enumerate(trs[0].findAll('td')[2:])]
        #seasonavg = [self._bold(colhead[i+2].getText()) + ": " + z.getText() for (i, z) in enumerate(trs[1].findAll('td')[1:])]
        careertotals = {colhead[k+2].getText(): v.getText() for (k, v) in enumerate(trs[0].findAll('td')[2:])}
        seasonavg = {colhead[k+2].getText(): v.getText() for (k, v) in enumerate(trs[1].findAll('td')[1:])}
        seasonavg = self._so(seasonavg)  # format both.
        careertotals = self._so(careertotals)
        # output time.
        irc.reply("{0} :: Season Averages :: {1}".format(self._bold(plrname), " | ".join([i for i in seasonavg])))
        irc.reply("{0} :: Career Totals :: {1}".format(self._bold(plrname), " | ".join([i for i in careertotals])))

    mlbcareerstats = wrap(mlbcareerstats, [('text')])
    
    def mlbgame(self, irc, msg, args, optplayer):
        """<player name"

        Try to fetch game stats (in or previous) for player.
        Ex: David Ortiz
        """

        # try and grab a player.
        url = self._pf('e', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        testtd = soup.find('td', text="This Game")
        if not testtd:
            irc.reply("ERROR: I did not find current/previous game stats for {0}".format(optplayer))
            return
        # continue
        plrname = soup.findAll('h1')[0].getText().encode('utf-8')
        # otherwise.
        venue = soup.find('div', attrs={'class':'game-details'})
        vtime = venue.find('div', attrs={'class':'time'}).getText(separator=' ').encode('utf-8')
        voverview = venue.find('div', attrs={'class':'overview'}).getText(separator=' ').encode('utf-8')
        # table
        table = soup.find('table', attrs={'class': 'tablehead', 'cellspacing': '1', 'cellpadding': '3'})
        # colhead.
        colhead = table.find('tr', attrs={'class': 'colhead'})
        chs = colhead.findAll('th')
        # row
        firstrow = table.findAll('tr')[1].findAll('td')
        # mate them together
        statz = " ".join([chs[i+1].getText() + ": " + v.getText() for (i, v) in enumerate(firstrow[1:])])

        irc.reply("{0} :: {1} :: {2} :: {3}".format(plrname, vtime, voverview, statz))
    
    mlbgame = wrap(mlbgame, [('text')])

    def mlbseasonstats(self, irc, msg, args, optyear, optplayer):
        """<year> <player name>

        Fetch season stats for player.
        Ex: 2010 Derek Jeter
        """

        # try and grab a player.
        url = self._pf('e', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # now replace the url so we can grab stats.
        url = url.replace('/mlb/player/_/id/', '/mlb/player/stats/_/id/')
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # error check.
        if "No statistics available." in html:
            irc.reply("Sorry, no stats are available for: {0}".format(optplayer))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        plrname = soup.findAll('h1')[0].getText().encode('utf-8')
        table = soup.find('table', attrs={'class': 'tablehead', 'cellspacing': '1', 'cellpadding': '3'})
        colhead = table.find('tr', attrs={'class': 'colhead'}).findAll('td')
        trs = table.findAll('tr', attrs={'class': re.compile('^evenrow$|^oddrow$')})
        # sanity check
        if len(trs) == 0:
            print "ERROR: Something went wrong grabbing stats. Check HTML formatting."
        # container
        st = collections.defaultdict(list)
        # iterate over their stats.
        for tr in trs:
            tds = tr.findAll('td')
            yr = tds[0].getText()
            tmp = {}  # tmp dict
            for (i, z) in enumerate(tds[1:]):  # mate them up with colhead. +1
                tmp[colhead[i+1].getText()] = z.getText()  # inject.
            # once done, append tmp to st.
            st[int(yr)].append(tmp)
        # now lets grab the year.
        outstat = st.get(optyear)
        # make sure we have that year.
        if not outstat:
            irc.reply("ERROR: I did not find stats for {0} in {1}.".format(plrname, optyear))
            return
        # lets format output.
        outstr = []
        # iterate over each item in the year.
        for q in outstat:  # each item here is going to be a dictionary.
            outstr.append("{0}".format(self._ul(q['TEAM'])))
            # we do this a little different than normal stats.
            #for (k, v) in q.items():  # stat items.
            #   if k != 'TEAM':  # team injected above
            #       outstr.append("{0}: {1}".format(self._bold(k), v))
            t = {k: v for (k, v) in q.items() if k != 'TEAM'}  # put in dict.
            t = self._so(t)  # format it.
            outstr.extend(t)  # must extend (not append) list
        # finally, output
        irc.reply("{0} :: {1} Stats :: {2}".format(self._bold(plrname), optyear, " ".join(outstr)))

    mlbseasonstats = wrap(mlbseasonstats, [('int'), ('text')])

    def mlbplayerinfo(self, irc, msg, args, optplayer):
        """<player name>

        Display information about MLB player.
        Ex: Derek Jeter
        """

        # try and grab a player.
        url = self._pf('e', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        div = soup.find('div', attrs={'class': 'mod-content'})
        if not div:
            irc.reply("ERROR: Could not find player info for: {0}. Check HTML.".format(optplayer))
            return
        # find their name.
        pname = div.find('h1')
        if not pname:
            irc.reply("ERROR: Could not find player info for: {0}. Check HTML.".format(optplayer))
            return
        pdiv = div.find('div', attrs={'class': 'player-bio'})
        if not pdiv:
            irc.reply("ERROR: Could not find player info for: {0}. Check HTML.".format(optplayer))
            return
        # now output.
        irc.reply("{0} :: {1}".format(self._bold(pname.getText().encode('utf-8')), pdiv.getText(separator=' ').encode('utf-8')))

    mlbplayerinfo = wrap(mlbplayerinfo, [('text')])

    def mlbgamestats(self, irc, msg, args, optplayer):
        """<player name>

        Fetch gamestats for player from current or past game.
        Ex: Derek Jeter
        """

        # try and grab a player.
        url = self._pf('e', optplayer)
        if not url:
            irc.reply("ERROR: I could not find a player page for: {0}".format(optplayer))
            # lets try to help them out with similar names.
            sp = self._similarPlayers(optplayer)
            if sp:  # if we get something back, lets return the fullnames.
                irc.reply("Possible suggestions: {0}".format(" | ".join([i['fullname'].title() for i in sp])))
            # now exit regardless.
            return
        # we do have url now. fetch it.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return None
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        playername = soup.find('div', attrs={'class': 'mod-content'}).find('h1').getText()
        maintable = soup.find('table', attrs={'class': 'player-profile-container'})
        if not maintable:  # sanity check.
            irc.reply("ERROR: Could not find PREVIOUS or CURRENT game. Check formatting on HTML.")
            return
        # we did find the maintable.
        mtheader = maintable.find('div', attrs={'class': 'mod-header'}).find('h4').getText()
        # have to look at what's in mtheader to determine the statline. we could probably consolidate this but
        # its easier for me when I have to debug these.
        if 'PREVIOUS GAME' in mtheader:  # previous game.
            # find the details of the previous game.
            gamedetails = maintable.find('div', attrs={'class': 'game-details'})
            gametime = gamedetails.find('div', attrs={'class': 'time'}).getText(separator=' ')
            gameaway = gamedetails.find('div', attrs={'class': 'team team-away'}).getText(separator=' ')
            gamehome = gamedetails.find('div', attrs={'class': 'team team-home'}).getText(separator=' ')
            gamescore = gamedetails.find('div', attrs={'class': 'scoreboard'}).getText(separator=' ')
            prevgametable = maintable.find('table', attrs={'class': 'tablehead'})
            prevcolhead = prevgametable.find('tr', attrs={'class': 'colhead'}).findAll('th')
            prevgame = prevgametable.findAll('tr')[1].findAll('td')
            if prevgame[0].getText() != "This Game":
                irc.reply("ERROR: I do not have previous game stats for {0} ({1}). Perhaps the player did not play in the game?".format(playername, gametime))
                return
            #statline = [self._bold(prevcolhead[i+1].getText()) + ": " + x.getText() for (i, x) in enumerate(prevgame[1:])]
            statline = {prevcolhead[i+1].getText(): x.getText() for (i, x) in enumerate(prevgame[1:])}
            statline = self._so(statline)
            irc.reply("{0} :: {1} ({2} @ {3}) :: {4}".format(self._bold(playername), gametime, gameaway, gamehome, " ".join(statline)))
        elif "CURRENT GAME" in mtheader:
            gamedetails = maintable.find('div', attrs={'class': 'game-details'})
            gametime = gamedetails.find('div', attrs={'class': 'time'}).getText(separator=' ')
            gameaway = gamedetails.find('div', attrs={'class': 'team team-away'}).getText(separator=' ')
            gamehome = gamedetails.find('div', attrs={'class': 'team team-home'}).getText(separator=' ')
            # gamescore = gamedetails.find('div', attrs={'class': 'scoreboard'}).getText(separator=' ')
            curgametable = maintable.find('table', attrs={'class': 'tablehead'})
            curcolhead = curgametable.find('tr', attrs={'class': 'colhead'}).findAll('th')
            curgame = curgametable.findAll('tr')[1].findAll('td')
            if curgame[0].getText() != "This Game":
                irc.reply("ERROR: I do not have current game stats for {0} ({1}). Perhaps the player is not active?".format(playername, gametime))
                return
            #statline = [self._bold(curcolhead[i+1].getText()) + ": " + x.getText() for (i, x) in enumerate(curgame[1:])]
            statline = {curcolhead[i+1].getText(): x.getText() for (i, x) in enumerate(curgame[1:])}
            statline = self._so(statline)
            irc.reply("{0} :: {1} ({2} @ {3}) :: {4}".format(self._bold(playername), gametime, gameaway, gamehome, " ".join(statline)))
        else:
            irc.reply("ERROR: Could not find PREVIOUS or CURRENT game. Check formatting on HTML.")

    mlbgamestats = wrap(mlbgamestats, [('text')])

Class = MLB
