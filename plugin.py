# -*- coding: utf-8 -*-
##
# Copyright (c) 2012-2013, spline
# All rights reserved.
#
#
###
# my libs.
from BeautifulSoup import BeautifulSoup
import re
import collections
import datetime
import random
import sqlite3
from itertools import groupby, count
import os.path
from base64 import b64decode
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
        for k, g in groupby(iterable, lambda x:c.next()//size):
            yield g

    def _validate(self, date, format):
        """Return true or false for valid date based on format."""

        try:
            datetime.datetime.strptime(str(date), format) # format = "%m/%d/%Y"
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
                page = utils.web.getUrl(url)
            return page
        except utils.web.Error as e:
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

    def _millify(self, num):
        """Turns a number like 1,000,000 into 1M."""

        for unit in ['','k','M','B','T']:
            if num < 1000.0:
                return "%3.3f%s" % (num, unit)
            num /= 1000.0

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
            # query = "SELECT %s FROM mlb WHERE %s='%s'" % (db, column, optteam)
            query = "SELECT %s FROM mlb WHERE %s=?" % (db, column)
            # cursor.execute(query)
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

        oDay = (datetime.datetime(2014, 03, 31) - datetime.datetime.now()).days
        irc.reply("{0} day(s) until 2014 MLB Opening Day.".format(oDay))

    mlbcountdown = wrap(mlbcountdown)

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

    def mlbstreaks(self, irc, msg, args):
        """
        Display this year's longest hitstreaks.
        """

        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy9oaXR0aW5nc3RyZWFrcw==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        title = soup.find('h1', attrs={'class':'h2'}).getText()
        div = soup.find('div', attrs={'id':'my-players-table'})
        table = div.find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr', attrs={'class':re.compile('(odd|even)row.*')})
        # container for output.
        mlbstreaks = collections.defaultdict(list)
        # each row is a player. stathead has league.
        for row in rows:
            league = row.findPrevious('tr', attrs={'class':'stathead'})
            tds = [item.getText() for item in row.findAll('td')]
            player = tds[0]
            streak = tds[2].strip(' games')
            mlbstreaks[league.getText()].append("{0} ({1})".format(player, streak))
        # output now.
        irc.reply("{0}".format(self._blue(title)))
        for i, x in mlbstreaks.items():
            irc.reply("{0} :: {1}".format(self._bold(i), " | ".join(x)))

    mlbstreaks = wrap(mlbstreaks)

    def mlbplayoffchances(self, irc, msg, args, optteam):
        """<team>
        Display team's current playoff chances, ws chances, % to obtain seeds, RPI and SOS.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build url and fetch.
        url = self._b64decode('aHR0cDovL3d3dy5zcG9ydHNjbHVic3RhdHMuY29tL01MQi5odG1s')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('table', attrs={'id':'list'})
        rows = table.findAll('tr', attrs={'class': re.compile('^team.*?')})
        # dict container for output.
        playoffs = collections.defaultdict(list)
        # each row is a team.
        for row in rows:
            tds = [item.getText() for item in row.findAll('td')]  # save time/space doing this.
            team = tds[0].lower()  # to match for translate team below.
            team = self._translateTeam('team', 'playoffs', team)  # translate to mate with optteam.
            # make the string to append as value below.
            appendString = "make playoffs: {0} | win WS: {1} | % to obtain seed # :: 1. {2} 2. {3} 3. {4} 4. {5} 5. {6} | RPI: {7} | SOS: {8}".format(\
                    self._bold(tds[9]), self._bold(tds[12]), self._bold(tds[16]), self._bold(tds[17]), self._bold(tds[18]), self._bold(tds[19]),\
                    self._bold(tds[20]), self._bold(tds[32]), self._bold(tds[33]))
            playoffs[team] = appendString
        # output time.
        output = playoffs.get(optteam)
        if not output:
            irc.reply("ERROR: I could not find playoff stats for: {0}.".format(optteam))
            return
        else:  # if we find it.
            irc.reply("{0} chances :: {1}".format(self._red(optteam), output))

    mlbplayoffchances = wrap(mlbplayoffchances, [('somethingWithoutSpaces')])

    def mlbpitcher(self, irc, msg, args, optteam):
        """<team>
        Displays current pitcher(s) and stats in active or previous game for team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build url and fetch scoreboard.
        url = self._b64decode('aHR0cDovL3Njb3Jlcy5lc3BuLmdvLmNvbS9tbGIvc2NvcmVib2FyZA==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process scoreboard.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        games = soup.findAll('div', attrs={'id': re.compile('.*?-gamebox')})
        # container to put all of the teams in.
        teamdict = collections.defaultdict()
        # process each "game" (two teams in each)
        for game in games:
            teams = game.findAll('p', attrs={'class':'team-name'})
            for team in teams:  # each game has two teams.
                ahref = team.find('a')['href']
                teamname = ahref.split('/')[7].lower()  # will be lowercase.
                teamname = self._translateTeam('team', 'eshort', teamname)  # fix the bspn discrepancy.
                teamid = team['id'].replace('-aNameOffset', '').replace('-hNameOffset', '')  # just need the gameID.
                teamdict.setdefault(str(teamname), []).append(teamid)
        # grab the gameid. fetch.
        teamgameids = teamdict.get(optteam)
        # sanity check before we grab the game.
        if not teamgameids:
            # self.log.info("ERROR: I got {0} as a team. I only have: {1}".format(optteam, str(teamdict)))
            irc.reply("ERROR: No upcoming/active games with: {0}".format(optteam))
            return
        # we have gameid. refetch boxscore for page.
        # now we fetch the game box score to find the pitchers.
        # everything here from now on is on the actual boxscore page.
        for teamgameid in teamgameids:  # we had to do foreach due to doubleheaders.
            url = self._b64decode('aHR0cDovL3Njb3Jlcy5lc3BuLmdvLmNvbS9tbGIvYm94c2NvcmU=') + '?gameId=%s' % (teamgameid)
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
            # now process the boxscore.
            soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
            pitcherpres = soup.findAll('th', text='Pitchers')
            # defaultdict to put key: team value: pitchers.
            teampitchers = collections.defaultdict()
            # should be two, one per team.
            if len(pitcherpres) != 2:  # game is too far from starting.
                if "Box Score not available." in html:  # sometimes the boxscore is not up.
                    pstring = "Box Score not available."
                else:
                    pitchers = soup.find('div', attrs={'class': 'line-score clear'})
                    if not pitchers:  # horrible and sloppy but should work.
                        pstring = "Error."
                    else:
                        startingpitchers = pitchers.findAll('p')
                        if len(startingpitchers) != 3:  # 3 rows, bottom 2 are the pitchers.
                            pstring = "Error."
                        else:  # minimal but it should stop most errors.
                            sp1, sp2 = startingpitchers[1], startingpitchers[2]
                            gameTime = soup.find('p', attrs={'id':'gameStatusBarText'})  # find time.
                            pstring = "{0} vs. {1}".format(sp1.getText(), sp2.getText())
                            if gameTime:  # add gametime if we have it.
                                pstring += " {0}".format(gameTime.getText())
                # now that we've processed above, append to the teampitchers dict.
                teampitchers.setdefault(str(optteam), []).append(pstring)
            else:  # we have the starting pitchers.
                for pitcherpre in pitcherpres:
                    pitchertable = pitcherpre.findParent('table')
                    pitcherrows = pitchertable.findAll('tr', attrs={'class': re.compile('odd player-.*?|even player-.*?')})
                    for pitcherrow in pitcherrows:  # one pitcher per row.
                        tds = pitcherrow.findAll('td')  # list of all tds.
                        pitchername = self._bold(tds[0].getText().replace('  ',' '))  # fix doublespace.
                        pitcherip = self._bold(tds[1].getText()) + "ip"
                        pitcherhits = self._bold(tds[2].getText()) + "h"
                        pitcherruns = self._bold(tds[3].getText()) + "r"
                        pitcherer = self._bold(tds[4].getText()) + "er"
                        pitcherbb = self._bold(tds[5].getText()) + "bb"
                        pitcherso = self._bold(tds[6].getText()) + "k"
                        pitcherhr = self._bold(tds[7].getText()) + "hr"
                        pitcherpcst = self._bold(tds[8].getText()) + "pc"
                        pitcherera = self._bold(tds[9].getText()) + "era"
                        team = pitcherrow.findPrevious('tr', attrs={'class': 'team-color-strip'}).getText()
                        # must translate team using fulltrans.
                        team = self._translateTeam('team', 'fulltrans', team)
                        # output string for the dict below.
                        pstring = "{0} - {1} {2} {3} {4} {5} {6} {7} {8}".format(pitchername, pitcherip, pitcherhits,\
                                                                                 pitcherruns, pitcherer, pitcherbb, \
                                                                                 pitcherso, pitcherhr, pitcherpcst, \
                                                                                 pitcherera)
                        teampitchers.setdefault(str(team), []).append(pstring)  # append into dict.
            # now, lets attempt to output.
            output = teampitchers.get(optteam, None)
            if not output:  # something went horribly wrong if we're here.
                irc.reply("ERROR: No pitchers found for {0}. Check when the game is active or finished, not before.".format(optteam))
                return
            else:  # ok, things did work.
                irc.reply("{0} :: {1}".format(self._red(optteam), " | ".join(output)))

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
            colhead = player.findPrevious('tr', attrs={'class':'stathead'})
            tds = [item.getText() for item in player.findAll('td')]
            appendString = "{0}. {1}".format(tds[0], tds[1], tds[2])
            cyyoung[str(colhead.getText())].append(appendString)  # now append.
        # output time.
        for i, x in cyyoung.iteritems():
            irc.reply("{0} :: {1}".format(self._red(i), " | ".join([item for item in x])))

    mlbcyyoung = wrap(mlbcyyoung)

    def mlbtrademachine(self, irc, msg, args):
        """
        Use Elkund-like powers to generate a trade between two teams.
        """

        # our array to pickfrom. references yahoo.
        teams = [
            'bal', 'bos', 'chw', 'cle', 'det', 'hou',
            'kan', 'laa', 'min', 'nyy', 'oak', 'sea',
            'tam', 'tex', 'ari', 'atl', 'chc', 'cin',
            'col', 'lad', 'mia', 'mil', 'nym', 'phi',
            'pit', 'sdg', 'sfo', 'stl', 'was', 'tor' ]

        twoteams = random.sample(teams, 2)  # grab two teams, randomly.
        #twoteamplayers = collections.defaultdict()  # setup defaultdict for team = key, values = players
        twoteamplayers = collections.defaultdict(list)
        # now we go to each team's roster and fill them up.
        for pickTeam in twoteams:
            # create url and fetch
            url = self._b64decode('aHR0cDovL3Nwb3J0cy55YWhvby5jb20vbWxiL3RlYW1z') + '/%s/roster' % pickTeam
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
            # now process the html.
            soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
            bbteam = soup.find('div', attrs={'class':'info'}).find('h1', attrs={'itemprop':'name'})
            #div = soup.find('div', attrs={'id':'team-roster'})  # roster div
            rows = soup.findAll('th', attrs={'class':'title', 'scope':'row'})
            # each row is a player.
            for row in rows:
                player = row.getText().encode('utf-8')  # players are last, first. we split+encode below.
                playersplit = player.split(',', 1)  # split on last, first so we can reverse below.
                player = "{0} {1}".format(playersplit[1].strip(), playersplit[0].strip())
                twoteamplayers[bbteam.getText()].append(player)
        # now we need to pick the player(s)
        outlist = []  # list will store: 0. team 1. players 2. team 3. players.
        for x, y in twoteamplayers.iteritems():
            randnum = random.randint(1, 3)  # number of players. 1-3
            randplayers = random.sample(y, randnum)  # use to randomly fetch players.
            outlist.append(x)  # append team.
            outlist.append(", ".join(randplayers))  # append player(s)
        # finally, output.
        output = "{0} :: The {1} trade {2} to the {3} for {4}".format(self._red("MLB TRADE MACHINE"),\
                self._bu(outlist[0]), self._bold(outlist[1]), self._bu(outlist[2]), self._bold(outlist[3]))
        irc.reply(output)

    mlbtrademachine = wrap(mlbtrademachine)

    def mlbheadtohead(self, irc, msg, args, optteam, optopp):
        """<team> <opp>
        Display the record between two teams head-to-head.
        Ex: NYY BOS
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # test for valid teams.
        optopp = self._validteams(optopp)
        if not optopp:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # test for similarity
        if optteam == optopp:
            irc.reply("ERROR: You must specify two different teams.")
            return
        # build and fetch url.
        teamString = self._translateTeam('cbs', 'team', optteam)  # need cbs string for team. must be uppercase.
        url = self._b64decode('aHR0cDovL3d3dy5jYnNzcG9ydHMuY29tL21sYi90ZWFtcy9zY2hlZHVsZQ==') + '/%s/' % teamString.upper()
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.findAll('table', attrs={'class':'data'})[1]
        rows = table.findAll('tr', attrs={'class': re.compile('^row.*?')})
        # container for output.
        winloss = {}
        for row in rows:  # one per game.
            tds = row.findAll('td')
            date = tds[0].getText().replace('  ', ' ').strip()  # trans date.
            if tds[1].getText().startswith('@'):  # vs or @ team.
                vsorat = "@"
            else:
                vsorat = "vs. "
            oppteam = tds[1].find('a')['href'].split('/')[4]  # find opp in / / href.
            oppteam = self._translateTeam('team', 'cbs', oppteam.lower())  # translate to mate with optteam. must be lower.
            wl = tds[2].getText().replace('  ', ' ').strip()  # score here, remove doublespace.
            # we need a win or loss since PPD = useless/played later so we skip.
            if wl.startswith('Lost') or wl.startswith('Won'):
                wldict = {}  # dict for values.
                if wl.startswith('Lost'):
                    wldict['winloss'] = 'L'
                elif wl.startswith('Won'):
                    wldict['winloss'] = 'W'
                wldict['date'] = date
                wldict['vsorat'] = vsorat
                wldict['score'] = wl.replace('Lost', 'L').replace('Won', 'W')  # some translation for output.
                winloss.setdefault(oppteam, []).append(wldict)  # now add it all.
        # small sanity check here.
        if len(winloss) == 0:
            irc.reply("ERROR: I have not found any played games for: {0}".format(optteam))
            return
        # output time.
        output = winloss.get(optopp)  # key is opponent's team.
        if not output:  # team did not play any games vs opp.
            irc.reply("ERROR: I did not find any games between {0} and {1}.".format(optteam, optopp))
            return
        else:  # we do have a team/games.
            wins = self._bold(len([item for item in output if item['winloss'] == "W"]))  # count wins, bold.
            losses = self._bold(len([item for item in output if item['winloss'] == "L"]))  # count losses, bold.
            games = " | ".join([item['date'] + ", " + item['vsorat'] + optopp + " (" + item['score'] + ")" for item in output])
            outstring = "{0} vs {1} {2}-{3} | {4}".format(self._red(optteam), self._red(optopp), wins, losses, games)
            irc.reply(outstring)

    mlbheadtohead = wrap(mlbheadtohead, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbseries(self, irc, msg, args, optteam, optopp):
        """<team> <opp>
        Display the remaining games between TEAM and OPP in the current schedule.
        Ex: NYY TOR
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # test for valid teams.
        optopp = self._validteams(optopp)
        if not optopp:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # fetch url.
        teamString = self._translateTeam('cbs', 'team', optteam)  # need cbs string for team. must be uppercase.
        url = self._b64decode('aHR0cDovL3d3dy5jYnNzcG9ydHMuY29tL21sYi90ZWFtcy9zY2hlZHVsZQ==') + '/%s/' % teamString.upper()
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # http://www.cbssports.com/mlb/teams/schedule/NYY/
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.findAll('table', attrs={'class':'data'})[1]
        rows = table.findAll('tr', attrs={'class': re.compile('^row.*?')})
        # container for output.
        winloss = []
        for row in rows:  # one per game.
            tds = row.findAll('td')
            oppteam = tds[1].find('a')['href'].split('/')[4]  # find opp in / / href.
            oppteam = self._translateTeam('team', 'cbs', oppteam.lower())  # translate to mate with optteam. must be lower.
            if optopp == oppteam:  # match input opp to what we found.
                date = tds[0].getText().replace('  ', ' ').strip()  # trans date.
                if tds[1].getText().startswith('@'):  # vs or @ team.
                    vsorat = "@"
                else:
                    vsorat = "vs."
                score = tds[2].getText().replace('  ', ' ').strip()  # score here, remove doublespace.
                # if Lost, Won or Post found, game was played. Skip over those.
                if score.startswith('Lost') or score.startswith('Won') or score.startswith('Post'):
                    continue
                else:  # actually add to the list.
                    winloss.append("{0} {1} {2} {3}".format(date, score, vsorat, optopp))
        # now prepare to output.
        if len(winloss) > 0:  # we found remaining games.
            descstring = " | ".join([item for item in winloss])
            irc.reply("There are {0} games remaining between {1} and {2} :: {3}".format(self._red(len(winloss)),\
                self._bold(optteam), self._bold(optopp), descstring))
        else:  # no remaining games found.
            irc.reply("I do not see any remaining games between: {0} and {1} in the {2} schedule.".format(\
                self._bold(optteam), self._bold(optopp), datetime.date.today().year))

    mlbseries = wrap(mlbseries, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbejections(self, irc, msg, args):
        """
        Display the total number of ejections and five most recent for the MLB season.
        """

        # build and fetch url.
        url = self._b64decode('aHR0cDovL3BvcnRhbC5jbG9zZWNhbGxzcG9ydHMuY29tL2hpc3RvcmljYWwtZGF0YS8=') + str(datetime.datetime.now().year) + '-mlb-ejection-list'
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process HTML.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        ejectedTitle = soup.find('span', attrs={'id':'sites-page-title'}).getText()
        ejectedTotal = soup.find('div', attrs={'class':'sites-list-showing-items'}).find('span').getText()
        table = soup.find('table', attrs={'id':'goog-ws-list-table', 'class':'sites-table goog-ws-list-table'})
        rows = table.findAll('tr')[1:]  # last 5. header row is 0.
        # last sanity check.
        if len(rows) == 0:
            irc.reply("Sorry, no ejections have been found for this season.")
            return
        # now that this is done.. containers for output.
        append_list = []
        umpcounter = collections.Counter()
        playercounter = collections.Counter()
        # each row is an ejection.
        for row in rows:
            tds = row.findAll('td')
            date = tds[0].getText()
            umpname = tds[4].getText()  # fix umpname below.
            if "," in umpname:  # if umpname is last, first
                umpname = umpname.split(',', 1)  # split on comma and rejoin.
                umpname = "{0} {1}".format(umpname[1].strip(), umpname[0].strip())
            else:  # just strip the spaces.
                umpname = umpname.strip()
            ejteam = tds[5].getText()
            ejected = tds[7].getText()
            date = self._dtFormat('%m/%d', date, '%B %d, %Y')  # conv date to smaller one
            # update our counters
            umpcounter[umpname] += 1
            playercounter[ejected] += 1
            # finally append to list.
            append_list.append("{0} - {1} ejected {2} ({3})".format(date, umpname, ejected, ejteam))
        # prepare output.
        irc.reply("{0} :: {1} ejections this season.".format(self._bold(ejectedTitle), self._red(ejectedTotal)))
        irc.reply("Umps with most ejections :: {0}".format(" | ".join([k + "(" + str(v) + ")" for (k,v) in umpcounter.most_common(3)])))
        irc.reply("Players ejected most :: {0}".format(" | ".join([k + "(" + str(v) + ")" for (k,v) in playercounter.most_common(3)])))
        irc.reply(" | ".join([item for item in append_list]))

    mlbejections = wrap(mlbejections)

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
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        lastDate = soup.findAll('span', attrs={'class': 'time'})[0]  # used for days since.
        divs = soup.findAll('div', attrs={'class': 'entry'})
        # output list.
        arrestlist = []
        # each div is an arrest.
        for div in divs:
            title = div.find('h2').getText().encode('utf-8')
            datet = div.find('span', attrs={'class': 'time'}).getText().encode('utf-8')
            datet = self._dtFormat("%m/%d", datet, "%B %d, %Y")  # translate date.
            arrestedfor = div.find('strong', text=re.compile('Team:'))  # this is tricky..
            if arrestedfor:  # not always there.
                matches = re.search(r'<strong>Team:.*?</strong>(.*?)<br />', arrestedfor.findParent('p').renderContents(), re.I| re.S| re.M)
                if matches:  # and not always found.
                    college = matches.group(1).replace('(MLB)','').encode('utf-8').strip()
                else:  # if we don't find anything, None is fine.
                    college = "None"
            else:  # just default to none.
                college = "None"
            arrestlist.append("{0} :: {1} - {2}".format(datet, title, college))
        # do some date math for days since.  (take last entry/date)
        delta = datetime.datetime.strptime(str(lastDate.getText()), "%B %d, %Y").date() - datetime.date.today()
        daysSince = abs(delta.days)
        # output
        irc.reply("{0} days since last MLB arrest".format(self._red(daysSince)))
        for each in arrestlist[0:6]:  # only show 6.
            irc.reply(each)

    mlbarrests = wrap(mlbarrests)

    def mlbstats(self, irc, msg, args, optlist, optplayer):
        """[--year YYYY] <player name>
        Display career totals and season averages for player.
        Specify --year YYYY for specific year vs career stats.
        Ex: Don Mattingly or --year 1988 Rickey Henderson
        """

        # we have to split the input because of how search is done.
        pnsplit = optplayer.split(' ', 1) # first, last(everything else)
        if len(pnsplit) is not 2:
            irc.reply("ERROR: You must give FIRST and LAST name in search. Ex: Don Mattingly")
            return
        # handle getopts (optinput)
        optyear = False
        if optlist:
            for (option, arg) in optlist:
                if option == 'year':
                    optyear = arg
        # build and fetch url. (reconstructs playername)
        url = self._b64decode('aHR0cDovL3NlYXJjaC5lc3BuLmdvLmNvbS8=') + "%s-%s" % (pnsplit[0], pnsplit[1])
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        # first parse the searchpage for the smartcard.
        if not soup.find('li', attrs={'class':'result mod-smart-card'}):  # didn't find the smartcard.
            irc.reply("ERROR: I didn't find a link for: {0}. This only works for MLB players and you might need to be more specific".format(optplayer))
            return
        playercard = soup.find('li', attrs={'class':'result mod-smart-card'})
        # for the rare occurences, check the url because we need a link to follow.
        if '/mlb/players/stats?playerId=' not in playercard.renderContents():
            irc.reply("ERROR: Could not find a link to career stats for: {0}".format(optplayer))
            return
        url = playercard.find('a', attrs={'href':re.compile('.*?/mlb/players/stats.*?')})['href']
        # make sure we have the link and fetch.
        if not url:  # no link found.
            irc.reply("ERROR: I didn't find the link I needed for career stats. Did something break?")
            return
        # we do have the link so lets refetch.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # now parse html the player's career page.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        playerName = soup.find('div', attrs={'class':'mod-content'}).find('h1').getText()  # playerName.
        table = soup.find('table', attrs={'class':'tablehead'})  # everything stems from the table.
        header = table.find('tr', attrs={'class':'colhead'}).findAll('td')  # columns to reference.
        # process html differently, depending on if we have optyear or not.
        if optyear:  # we have optyear. show specific year stats.
            seasonrows = table.findAll('tr', attrs={'class':re.compile('^oddrow$|^evenrow$')})  # find all outside the season+totals
            season_data = collections.defaultdict(list)  # key will be the year.
            # iterate over each season, store in k/v.
            for row in seasonrows:
                tds = row.findAll('td')
                for i, td in enumerate(tds):
                    season_data[int(tds[0].getText())].append("{0}: {1}".format(self._bold(header[i].getText()), td.getText()))
            # output time.
            outyear = season_data.get(optyear)
            if not outyear:  # no season found.
                irc.reply("ERROR: No stats found for {0} in {1}".format(playerName, optyear))
            else:  # found the season and print it.
                irc.reply("{0} :: {1}".format(playerName, " | ".join([item for item in outyear])))
        else:  # career stats not for a specific year.
            endrows = table.findAll('tr', attrs={'class':re.compile('^evenrow bi$|^oddrow bi$')})
            totals, seasonaverages = None, None
            for total in endrows:
                if total.find('td', text="Total"):
                    totals = total.findAll('td')
                if total.find('td', text="Season Averages"):
                    seasonaverages = total.findAll('td')
            # sometimes, the player is too new for totals/seasonaverages. bailout.
            if not totals and not seasonaverages:
                irc.reply("ERROR: I could not find totals and seasonaverages for: {0}. Perhaps the player is too new?".format(playerName))
                return
            # if we are set, remove the first td, but match up header via j+2
            del seasonaverages[0]
            del totals[0:2]
            # do the averages for output.
            seasonstring = " | ".join([self._bold(header[i+2].getText()) + ": " + td.getText() for i, td in enumerate(seasonaverages)])
            totalstring = " | ".join([self._bold(header[i+2].getText()) + ": " + td.getText() for i, td in enumerate(totals)])
            # output time.
            irc.reply("{0} :: Season Averages :: {1}".format(self._red(playerName), seasonstring))
            irc.reply("{0} :: Career Totals :: {1}".format(self._red(playerName), totalstring))

    mlbstats = wrap(mlbstats, [(getopts({'year':('int')})), ('text')])

    def mlbgamesbypos (self, irc, msg, args, optteam):
        """<team>
        Display a team's games by position.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL2xpbmV1cC9fL25hbWU=') + '/%s/' % optteam.lower()
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('td', attrs={'colspan':'2'}, text="GAMES BY POSITION").findParent('table')
        rows = table.findAll('tr', attrs={'class':re.compile('oddrow|evenrow')})
        # output list.
        append_list = []
        # each row is a position.
        for row in rows:
            playerPos = row.find('td').find('strong')
            playersList = playerPos.findNext('td')
            append_list.append("{0} {1}".format(self._bold(playerPos.getText()), playersList.getText()))
        # prepare time.
        descstring = " | ".join([item for item in append_list])
        output = "{0} (games by POS) :: {1}".format(self._red(optteam.upper()), descstring)
        # output.
        irc.reply(output)

    mlbgamesbypos = wrap(mlbgamesbypos, [('somethingWithoutSpaces')])

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
        table = soup.find('div', attrs={'class':'mod-content'}).find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr', attrs={'class':re.compile('^oddrow player.*|^evenrow player.*')})
        # k/v container for output.
        team_data = collections.defaultdict(list)
        # each row is a player, in a table of position.
        for row in rows:
            playerType = row.findPrevious('tr', attrs={'class':'stathead'})
            playerNum = row.find('td')
            playerName = playerNum.findNext('td').find('a')
            playerPos = playerName.findNext('td')
            team_data[playerType.getText()].append("{0} ({1})".format(playerName.getText(), playerPos.getText()))
        # output time.
        for i, j in team_data.iteritems():  # output one line per position.
            irc.reply("{0} {1} :: {2}".format(self._red(optteam.upper()), self._bold(i), " | ".join([item for item in j])))

    mlbroster = wrap(mlbroster, [getopts({'active':'','40man':''}), ('somethingWithoutSpaces')])

    def mlbrosterstats(self, irc, msg, args, optteam):
        """[team]
        Displays top 5 youngest/oldest teams.
        Optionally, use TEAM as argument to display roster stats/averages for MLB team.
        Ex: NYY
        """

        if optteam:  # if we want a specific team, validate it.
            optteam = self._validteams(optteam)
            if not optteam:  # team is not found in aliases or validteams.
                irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
                return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy9yb3N0ZXJz')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr')[2:]  # first two are headers.
        # use a list to store our ordereddicts.
        object_list = []
        # each row is a team.
        for row in rows:
            tds = row.findAll('td')
            team = tds[1].getText()
            rhb = tds[2].getText()
            lhb = tds[3].getText()
            sh = tds[4].getText()
            rhp = tds[5].getText()
            lhp = tds[6].getText()
            ht = tds[7].getText()
            wt = tds[8].getText()
            age = tds[9].getText()
            young = tds[10].getText()
            old = tds[11].getText()
            # create our string to append into the OD.
            aString = "RHB: {0}  LHB: {1}  SH: {2}  RHP: {3}  LHP: {4}  AVG HT: {5}  AVG WEIGHT: {6}  AVG AGE: {7}  YOUNGEST: {8}  OLDEST: {9}".format(\
                        rhb, lhb, sh, rhp, lhp, ht, wt, age, young, old)
            # each row (team) will go in the OD and append into
            d = collections.OrderedDict()
            d['team'] = self._translateTeam('team', 'ename', team)  # translate to our team.
            d['data'] = aString
            object_list.append(d)
        # output time.
        if optteam:  # if we have a team, validated above, output them.
            for each in object_list:
                if each['team'] == optteam:  # list will have all teams so we don't need to check
                    output = "{0} Roster Stats :: {1}".format(self._red(each['team']), each['data'])
            irc.reply(output)
        else:  # just show youngest and oldest.
            output = "{0} :: {1}".format(self._bold("5 Youngest MLB Teams:"), " | ".join([item['team'] for item in object_list[0:5]]))
            irc.reply(output)
             # above, first five are the youngest. oldest = last five.
            output = "{0} :: {1}".format(self._bold("5 Oldest MLB Teams:"), " | ".join([item['team'] for item in object_list[-6:-1]]))
            irc.reply(output)

    mlbrosterstats = wrap(mlbrosterstats, [optional('somethingWithoutSpaces')])

    def _format_cap(self, figure):
        """Format cap numbers for mlbpayroll command."""

        figure = figure.replace(',', '').strip()  # remove commas.
        if figure.startswith('-'):  # figure out if we're a negative number.
            negative = True
            figure = figure.replace('-','')
        else:
            negative = False
        # try and millify.
        try:
            figure = self._millify(float(figure))
        except:  # sometimes it breaks.
            figure = figure
        # reconstruct number below.
        if negative:
            figure = "-" + figure
        # now return
        return figure

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
        url = self._b64decode('aHR0cDovL3d3dy5zcG90cmFjLmNvbS9tbGIv') + '%s/team-payroll/' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        teamtitle = soup.find('title')
        tbody = soup.find('tbody')
        paytds = tbody.findAll('td', attrs={'class':'total team total-title'})
        # list for output.
        payroll = []
        # different rows applicable to payroll here.
        for paytd in paytds:
            row = paytd.findPrevious('tr')
            paytitle = row.find('td', attrs={'class': 'total team total-title'})
            payfigure = row.find('td', attrs={'class': 'total figure'})
            payfigure = self._format_cap(payfigure.getText())
            payroll.append("{0}: {1}".format(self._ul(paytitle.getText()), payfigure))
        # we need the last row. this is horrible but works.
        bottomrow = tbody.findAll('tr')
        bottomtds = bottomrow[-1].findAll('td')
        # take each TD, format the cap, all from last row.
        basesalary = self._format_cap(bottomtds[1].getText())
        signingbonus = self._format_cap(bottomtds[2].getText())
        otherbonus = self._format_cap(bottomtds[3].getText())
        totalpayroll = self._format_cap(bottomtds[4].getText())
        # now output.
        irc.reply("{0} :: Base Salaries {1} | Signing Bonuses {2} | Other Bonus {3} :: TOTAL PAYROLL {4}".format(\
            self._red(teamtitle.getText()), self._bold(basesalary), self._bold(signingbonus),\
                self._bold(otherbonus), self._bold(totalpayroll)))
        irc.reply("{0} :: {1}".format(self._red(teamtitle.getText()), " | ".join([item for item in payroll])))

    mlbpayroll = wrap(mlbpayroll, [('somethingWithoutSpaces')])

    def mlbweather(self, irc, msg, args, optteam):
        """<team>
        Display weather for MLB team at park they are playing at.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL3d3dy5wYXJrZmFjdG9ycy5jb20v')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity checking.
        if "an error occurred while processing this directive" in html:
            irc.reply("Something broke with parkfactors. Check back later.")
            return
        # need to do some mangling.
        html = html.replace('&amp;','&').replace('ARZ','ARI').replace('CHW','CWS').replace('WAS','WSH').replace('MLW','MIL')
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        h3s = soup.findAll('h3')
        # k/v container for output. key = team.
        mlbweather = collections.defaultdict(list)
        # each h3 is a game.
        for h3 in h3s:  # the html/formatting sucks.
            park = h3.find('span', attrs={'style':'float: left;'})
            factor = h3.find('span', attrs={'style': re.compile('color:.*?')})
            matchup = h3.findNext('h4').find('span', attrs={'style':'float: left;'})
            winddir = h3.findNext('img', attrs={'class':'rose'})
            winddir = (''.join(i for i in winddir['src'] if i.isdigit())).encode('utf-8')
            windspeed = h3.findNext('p', attrs={'class':'windspeed'}).find('span').getText().encode('utf-8')
            weather = h3.findNext('h5', attrs={'class':'l'})  #
            if weather.find('img', attrs={'src':'../images/roof.gif'}):
                weather = "[ROOF] " + weather.getText().strip().replace('.Later','. Later').replace('&deg;F','F ')
            else:
                weather = weather.getText().strip().replace('.Later','. Later').replace('&deg;F','F ')

            # now do some split work to get the dict with teams as keys.
            teams = matchup.getText().split(',', 1)  # NYY at DET, 1:05PM ET
            # now, left with TEAM at TEAM. foreach on both to append to dict.
            for team in teams[0].split('at'):  # ugly but works.
                mlbweather[team.strip()] = "{0}  at {1}({2})  Weather: {3}  Wind: {4}mph  ({5}deg)".format(\
                    self._ul(matchup.getText().encode('utf-8')), park.getText().encode('utf-8'),\
                        factor.getText().encode('utf-8'), weather.encode('utf-8'), windspeed, winddir)
        # finally, lets try and output.
        output = mlbweather.get(optteam)
        if output:  # team not found.
            irc.reply(output)
        else:  # team not found.
            irc.reply("ERROR: No weather found for: {0}. Perhaps the team is not playing?".format(optteam))

    mlbweather = wrap(mlbweather, [('somethingWithoutSpaces')])

    def mlbvaluations(self, irc, msg, args):
        """
        Display current MLB team valuations from Forbes.
        """

        # build and fetch url.
        url = self._b64decode('aHR0cDovL3d3dy5mb3JiZXMuY29tL21sYi12YWx1YXRpb25zL2xpc3Qv')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        updated = soup.find('small', attrs={'class':'fright'}).getText()
        tbody = soup.find('tbody', attrs={'id':'listbody'})
        rows = tbody.findAll('tr')
        # output list.
        object_list = []
        # one team per row.
        for row in rows:
            rank = row.find('td', attrs={'class':'rank'})
            team = rank.findNext('td')
            value = team.findNext('td')
            object_list.append("{0}. {1} {2}M".format(rank.getText(), team.find('h3').getText(), value.getText()))
        # output.
        irc.reply("{0} (in millions) :: {1}".format(self._red("Current MLB Team Values"), self._bold(updated)))
        irc.reply("{0}".format(" | ".join([item for item in object_list])))

    mlbvaluations = wrap(mlbvaluations)

    def mlbremaining(self, irc, msg, args, optteam):
        """<team>
        Display remaining games/schedule for a playoff contender.
        NOTE: Will only work closer toward the end of the season.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9odW50Zm9yb2N0b2Jlcg==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        tables = soup.findAll('table', attrs={'class':'tablehead', 'cellpadding':'3', 'cellspacing':'1', 'width':'100%'})
        # dict for output. key = team name.
        new_data = collections.defaultdict(list)
        # each table is a matchup.
        for table in tables:
            team = table.find('tr', attrs={'class':'colhead'}).find('td', attrs={'colspan':'6'})
            gr = table.find('tr', attrs={'class':'oddrow'})
            if team is not None and gr is not None: # horrible and cheap parse
                team = self._translateTeam('team', 'fulltrans', team.getText().title()) # full to short.
                new_data[team].append(gr.getText())
        # prepare to ouput
        output = new_data.get(optteam)
        if not output:  # no team found. might not be contender.
            irc.reply("{0} not listed. Not considered a playoff contender.".format(optteam))
        else:  # team is found.
            irc.reply("{0} :: {1}".format(self.bold(optteam), (" ".join(output))))

    mlbremaining = wrap(mlbremaining, [('somethingWithoutSpaces')])

    # !leaders nl|al|mlb <stat> [<year>]
    def mlbleaders(self, irc, msg, args, optlist, optleague, optcat, optstat, optyear):
        """[--postseason|--bottom] <mlb|nl|al> <statcategory> <statname> [year]
        Display MLB leaders in various stat categories.

        Use --postseason before to display postseason. Use --before to reverse the order.
        """

        # first, we declare our very long list of categories. used for validity/matching/url and the help.
        stats = {'batting':{'AB':['At Bats', '/sort/atBats'],
                            'R':['Runs', '/sort/runs'],
                            'H':['Hits', '/sort/hits'],
                            '2B':['Doubles', '/sort/doubles'],
                            '3B':['Triples', '/sort/triples'],
                            'HR':['Home Runs', '/sort/homeRuns'],
                            'RBI':['Runs Batted In', '/sort/RBIs'],
                            'SB':['Stolen Bases', '/sort/stolenBases'],
                            'CS':['Caught Stealing', '/sort/caughtStealing'],
                            'BB':['Walks', '/sort/walks'],
                            'SO':['Strikeouts', '/sort/strikeouts'],
                            'AVG':['Batting Average', '/sort'],
                            'OBP':['On Base Percentage', '/sort/onBasePct'],
                            'SLG':['Slugging Percentage', '/sort/slugAvg'],
                            'OPS':['OBP+SLG', '/sort/OPS'],
                            'WAR':['Wins Above Replacement', '/sort/WARBR'],
                            'GP':['Games played', '/sort/gamesPlayed/type/expanded'],
                            'TPA':['Total Plate Appearances', '/sort/plateAppearances/type/expanded'],
                            'PIT':['Number of Pitches', '/sort/pitches/type/expanded'],
                            'P/PA':['Pitches Per Plate Appearance', '/sort/pitchesPerPlateAppearance/type/expanded'],
                            'TB':['Total Bases', '/sort/totalBases/type/expanded'],
                            'XBH':['Extra Base Hits', '/sort/extraBaseHits/type/expanded'],
                            'HBP':['Hit By Pitch', '/sort/hitByPitch/type/expanded'],
                            'IBB':['Intentional Walks', '/sort/intentionalWalks/type/expanded'],
                            'GDP':['Grounded Into Double Plays', '/sort/GIDPs/type/expanded'],
                            'SH':['Sacrifice Hits', '/sort/sacHits/type/expanded'],
                            'SF':['Sacrifice Flies', '/sort/sacFlies/type/expanded'],
                            'RC':['Runs Created', '/sort/runsCreated/type/sabermetric'],
                            'RC27':['Runs Created Per 27 Outs', '/sort/runsCreatedPer27Outs/type/sabermetric'],
                            'ISOP':['Isolated Power', '/sort/isolatedPower/type/sabermetric'],
                            'SECA':['Secondary Average', '/sort/secondaryAvg/type/sabermetric'],
                            'GB':['Ground Balls', '/sort/groundBalls/type/sabermetric'],
                            'FB':['Fly Balls', '/sort/flyBalls/type/sabermetric'],
                            'G/F':['Ground Ball to Fly Ball Ratio', '/sort/groundToFlyRatio/type/sabermetric'],
                            'AB/HR':['At Bats Per Home Run', '/sort/atBatsPerHomeRun/type/sabermetric'],
                            'BB/PA':['Walks Per Plate Appearance', '/sort/walksPerPlateAppearance/type/sabermetric'],
                            'BB/K':['Walk to Strikeout Ratio', '/sort/walkToStrikeoutRatio/type/sabermetric'] },
                'fielding':{'FULL':['Innings', '/sort/fullInningsPlayed'],
                            'TC':['Total Chances', '/sort/totalChances'],
                            'PO':['Putouts', '/sort/putouts'],
                            'A':['Assists', '/sort/assists'],
                            'E':['Errors', '/sort/errors'],
                            'DP':['Double Plays', '/sort/doublePlays'],
                            'FPCT':['Fielding %', '/order/false'],
                            'RP':['Range Factor', '/sort/rangeFactor'],
                            'DWAR':['Defensive Wins Above Replacement', '/sort/defWARBR'] },
                'pitching': {'IP':['Innings Pitched', '/sort/thirdInnings'],
                             'H':['Hits', '/sort/hits'],
                             'R':['Runs', '/sort/runs'],
                             'ER':['Earned Runs', '/sort/earnedRuns'],
                             'BB':['Walks', '/sort/walks'],
                             'SO':['Strikeouts', '/sort/strikeouts'],
                             'W':['Wins', '/sort/wins'],
                             'L':['Losses', '/sort/losses'],
                             'SV':['Saves', '/sort/saves'],
                             'BKLSV':['Blown Saves', '/sort/blownSaves'],
                             'WAR':['Wins Above Replacement', '/sort/WARBR'],
                             'WHIP':['Walks/Hits per IP', '/sort/WHIP'],
                             'ERA':['Earned Run Average', '/order/true'],
                             'CG':['Complete Games', '/sort/completeGames/type/expanded'],
                             'SHO':['Shutouts', '/sort/shutouts/type/expanded'],
                             'TBF':['Total Batters Faced', '/sort/battersFaced/type/expanded'],
                             'GF':['Games Finished', '/sort/finishes/type/expanded'],
                             'SVO':['Save Opportunities', '/sort/saveOpportunities/type/expanded'],
                             'SH':['Sac Bunts', '/sort/sacBunts/type/expanded'],
                             'SF':['Sac Flies', '/sort/sacFlies/type/expanded'],
                             'HBP':['Hit By Pitch', '/sort/battersHit/type/expanded'],
                             'GDP':['Grounded Into DP', '/sort/GIDPs/type/expanded'],
                             'WP':['Wild Pitches', '/sort/wildPitches/type/expanded'],
                             'BK':['Balks', '/sort/balks/type/expanded'],
                             'QS':['Quality Starts', '/sort/qualityStarts/type/expanded'],
                             'QS%':['Quality Start %', '/sort/QSPct/type/expanded'],
                             'K/BB':['Strikeout to walk ratio', '/sort/strikeoutToWalkRatio/type/expanded-2'],
                             'K/9':['Strikeouts Per Nine innings', '/sort/strikeoutsPerNineInnings/type/expanded-2'],
                             'PITCHES':['Number of Pitches', '/sort/pitches/type/expanded-2'],
                             'P/PA':['Pitches Per Plate Appearance', '/sort/pitchesPerPlateAppearance/type/expanded-2'],
                             'P/IP':['Pitches Per Inning', '/sort/pitchesPerInning/type/expanded-2'],
                             'W%':['Winning Percentage', '/sort/winPct/type/expanded-2'],
                             'AGS':['Average Game Score', '/sort/avgGameScore/type/expanded-2'],
                             'GB':['Ground Balls', '/sort/groundBalls/type/expanded-2'],
                             'FB':['Fly Balls', '/sort/flyBalls/type/expanded-2'],
                             'G/F':['Ground Ball to Fly Ball Ratio', '/sort/groundToFlyRatio/type/expanded-2'],
                             'RS':['Run Support Average (per start)', '/sort/runSupportPerStart/type/expanded-2'],
                             'ERC':['Component ERA', '/sort/ERC/type/sabermetric'],
                             'ERC%':['Component ERA Ratio', '/sort/ERCratio/type/sabermetric'],
                             'DIPS':['Defense-independent ERA', '/sort/DIPSERA/type/sabermetric'],
                             'DIP%':['Defense-independent ERA Ratio', '/sort/DIPSratio/type/sabermetric'],
                             'TLoss':['Tough Losses', '/sort/toughLosses/type/sabermetric'],
                             'CWin':['Cheap Wins', '/sort/cheapWins/type/sabermetric'],
                             'PFR':['Power/Finesse Ratio', '/sort/PFR/type/sabermetric'],
                             'BABIP':['Batting Average on Balls In Play', '/sort/BIPA/type/sabermetric'],
                             'TB':['Opponent Total Bases', '/sort/opponentTotalBases/type/opponent-batting'],
                             '2B':['Doubles', '/sort/doubles/type/opponent-batting'],
                             '3B':['Triples', '/sort/triples/type/opponent-batting'],
                             'HR':['Home Runs', '/sort/homeRuns/type/opponent-batting'],
                             'RBI':['Runs Batted In', '/sort/RBIs/type/opponent-batting'],
                             'IBB':['Intentional Walks', '/sort/intentionalWalks/type/opponent-batting'],
                             'SB':['Stolen Bases', '/sort/stolenBases/type/opponent-batting'],
                             'CS':['Caught Stealing', '/sort/caughtStealing/type/opponent-batting'],
                             'CS%':['Caught Stealing Percentage', '/sort/caughtStealingPct/type/opponent-batting'],
                             'BAA':['Opponents Batting Average', '/sort/opponentAvg/type/opponent-batting'],
                             'OBP':['Opponents On Base Percentage', '/sort/opponentOnBasePct/type/opponent-batting'],
                             'SLG':['Opponents Slugging Average', '/sort/opponentSlugAvg/type/opponent-batting'],
                             'OPS':['OPS', '/sort/opponentOPS/type/opponent-batting'] }
            }

        # must process getopts (optlist) input before anything.
        postseason, bottom = False, False
        if optlist:
            for (k, v) in optlist:
                if k == 'postseason':  # postseason stats.
                    postseason = True
                if k == 'bottom':  # reverse order.
                    bottom = True
        # handle league. check for valid.
        optleague = optleague.upper()  # lower to match.
        validleagues = {'MLB':'', 'NL':'/league/nl', 'AL':'/league/al'}
        if optleague not in validleagues:  # invalid league found.
            irc.reply("ERROR: '{0}' is an invalid league. Must specify {1}".format(optleague, " | ".join(validleagues.keys())))
            return
        # handle the category.
        optcat = optcat.lower()  # lower to match.
        if optcat not in stats:
            irc.reply("ERROR: '{0}' is an invalid category. Must be one of: {1}".format(optcat, " | ".join(stats.keys())))
            return
        # now handle the stats depending on the category.
        optstat = optstat.upper()  # upper to match.
        if optstat not in stats[optcat]:
            irc.reply("ERROR: '{0}' is an invalid {1} category. Valid: {2}".format(optstat, optcat, " | ".join(sorted(stats[optcat].keys()))))
            return
        # now we look if year was specified. stays false otherwise.
        if not optyear:  # optyear present?
            optyear = False  # no optyear.
        else:  # we do have optyear.
            if 2000 <= optyear <= datetime.datetime.now().year:  # valid year.
                optyear = optyear
            else:  # invalid year.
                irc.reply("ERROR: '{0}' is invalid. It must be between 2000 and the current year.".format(optyear))
                return

        # now we build URL.
        url = b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy8=') + optcat + '/_' # year/2012
        # add year if needed.
        if optyear:
            url += '/year/%s' % str(optyear)
        # post or regular season?
        if postseason:  # if postseason.
            url += '/seasontype/3'
        else:  # regular season.
            url += '/seasontype/2'
        url += validleagues[optleague]  # handle league (mlb|nl|al)
        url += stats[optcat][optstat][1]  # last, add on the url part of the stat..
        if bottom:  # if we want the bottom, the order is reversed.
            url += '/order/false'
        else:  # regular order (top->bottom)
            url += '/order/true'

        # now, with the url, fetch and return content.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity check before we can process html.
        if 'No results available based on the selected criteria.' in html:
            irc.reply("ERROR: No results available based on the selected criteria. If using a year, make sure that season/postseason has been played.")
            return
        # process HTML.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        div = soup.find('div', attrs={'class':'mod-content'})  # below we fetch the season.
        season = div.find('select', attrs={'class':'tablesm'}).find('option', attrs={'selected':'selected'}).getText()
        playerdiv = soup.find('div', attrs={'id':'my-players-table'})  # div for table.
        table = playerdiv.find('table', attrs={'class':'tablehead'})  # playerrows in here.
        #colhead = table.find('tr', attrs={'class':'colhead'}).findAll('td')  # table headers.
        rows = table.findAll('tr', attrs={'class':re.compile('(even|odd)row.*')})[0:10]  # top10 (or bottom10) only.
        # list to store players and stat.
        mlbstats = []
        # each row is a player
        for row in rows:
            player = row.findAll('td')[1].getText().encode('utf-8')  # 2nd td = player.
            stat = row.find('td', attrs={'class':'sortcell'}).getText()  # stat = sortcell.
            mlbstats.append("{0} ({1})".format(self._bold(player), stat))  # append them to list.
        # now we prepare the output.
        irc.reply("{0} {1} LEADERS IN {2}({3}) :: {4}".format(self._red(season), optleague, self._ul(optstat), stats[optcat][optstat][0], " | ".join(mlbstats)))

    mlbleaders = wrap(mlbleaders, [getopts({'postseason':'', 'bottom':''}), ('somethingWithoutSpaces'), ('somethingWithoutSpaces'), ('somethingWithoutSpaces'), optional('int')])

    def mlbplayoffs(self, irc, msg, args, optleague):
        """<AL|NL>
        Display playoff matchups if season ended today.
        """

        # validate league for url.
        optleague = optleague.upper()
        if optleague == "AL":
            url = b64decode('aHR0cDovL3d3dy5wbGF5b2Zmc3RhdHVzLmNvbS9tbGIvYW1lcmljYW5zdGFuZGluZ3MuaHRtbA==')
        elif optleague == "NL":
            url = b64decode('aHR0cDovL3d3dy5wbGF5b2Zmc3RhdHVzLmNvbS9tbGIvbmF0aW9uYWxzdGFuZGluZ3MuaHRtbA==')
        else:
            irc.reply("ERROR: league must be AL or NL.")
            return
        # build and fetch url.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        title = soup.findAll('h2')[1].getText()  # 2nd h2.
        rows = soup.findAll('tr', attrs={'valign':'top', 'align':'center'})[2:7]  # skip the 2 headers, grab the first 5.
        # list container we put teams in to later grab.
        teams = []
        # rows filtered above. each row is a team. we only have five here.
        for row in rows:
            team = row.find('td').getText()
            team = self._bold(team)
            teams.append(team)  # append so we can sort out later.
        # now prepare to output. have to order the matchups string.
        matchups = "(WC: {1} vs. {2}) vs. {0} || {3} vs. {4}".format(teams[0], teams[3], teams[4], teams[1], teams[2])
        irc.reply("{0} :: {1}".format(self._red(title), matchups))

    mlbplayoffs = wrap(mlbplayoffs, [('somethingWithoutSpaces')])

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
        table = soup.find('table', attrs={'data-crop':'50'})
        rows = table.findAll('tr')[1:11]  # skip first row (header) and get the next 10.
        # output container is a list.
        object_list = []
        # each row is a player.
        for row in rows:
            rank = row.find('td', attrs={'align':'right'})
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
        alvp = soup.find('h2', text="AL MVP Voting").findNext('table', attrs={'id':'AL_MVP_voting'}).findNext('a').text
        nlvp = soup.find('h2', text="NL MVP Voting").findNext('table', attrs={'id':'NL_MVP_voting'}).findNext('a').text
        alcy = soup.find('h2', text="AL Cy Young Voting").findNext('table', attrs={'id':'AL_Cy_Young_voting'}).findNext('a').text
        nlcy = soup.find('h2', text="NL Cy Young Voting").findNext('table', attrs={'id':'NL_Cy_Young_voting'}).findNext('a').text
        alroy = soup.find('h2', text="AL Rookie of the Year Voting").findNext('table', attrs={'id':'AL_Rookie_of_the_Year_voting'}).findNext('a').text
        nlroy = soup.find('h2', text="NL Rookie of the Year Voting").findNext('table', attrs={'id':'NL_Rookie_of_the_Year_voting'}).findNext('a').text
        almgr = soup.find('h2', text="AL Mgr of the Year Voting").findNext('table', attrs={'id':'AL_Mgr_of_the_Year_voting'}).findNext('a').text
        nlmgr = soup.find('h2', text="NL Mgr of the Year Voting").findNext('table', attrs={'id':'NL_Mgr_of_the_Year_voting'}).findNext('a').text
        # prepare output string.
        output = "{0} MLB Awards :: MVP: AL {1} NL {2}  CY: AL {3} NL {4}  ROY: AL {5} NL {6}  MGR: AL {7} NL {8}".format( \
            self._red(optyear), self._bold(alvp), self._bold(nlvp), self._bold(alcy), self._bold(nlcy),\
            self._bold(alroy), self._bold(nlroy), self._bold(almgr), self._bold(nlmgr))
        # actually output.
        irc.reply(output)

    mlbawards = wrap(mlbawards, [optional('int')])

    def mlbschedule(self, irc, msg, args, optteam):
        """<team>
        Display the last and next five upcoming games for team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # translate team for url.
        lookupteam = self._translateTeam('yahoo', 'team', optteam) # (db, column, optteam)
        # build and fetch url.
        url = self._b64decode('aHR0cDovL3Nwb3J0cy55YWhvby5jb20vbWxiL3RlYW1z') + '/%s/calendar/rss.xml' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity check.
        if "Schedule for" not in html:
            irc.reply("ERROR: Cannot find schedule. Broken url?")
            return
        # clean html up before attempting to parse.
        html = html.replace('<![CDATA[','')  #remove cdata
        html = html.replace(']]>','')  # end of cdata
        html = html.replace('EDT','')  # tidy up times
        html = html.replace('\xc2\xa0',' ')  # remove some stupid character.
        # now soup the actual html. BS cleans up the RSS because the HTML is junk.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        items = soup.find('channel').findAll('item')
        # list for output.
        append_list = []
        # we're going over semi-broken RSS here.
        for item in items:
            title = item.find('title').getText().strip()  # title is good.
            day, date = title.split(',')
            desc = item.find('description')  # everything in desc but its messy.
            desctext = desc.findAll(text=True)  # get all text, first, but its in a list.
            descappend = (''.join(desctext).strip())  # list transform into a string.
            if not descappend.startswith('@'):  # if something is @, it's before, but vs. otherwise.
                descappend = 'vs. ' + descappend
            descappend += " [" + date.strip() + "]"  # can't translate since Yahoo! sucks with the team names here.
            append_list.append(descappend)  # put all into a list.
        # prepare output string and output.
        descstring = " | ".join([item for item in append_list])
        irc.reply("{0} :: {1}".format(self._bold(optteam), descstring))

    mlbschedule = wrap(mlbschedule, [('somethingWithoutSpaces')])

    def mlbmanager(self, irc, msg, args, optteam):
        """<team>
        Display the manager for team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9tYW5hZ2Vycw==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        rows = soup.findAll('tr', attrs={'class':re.compile('oddrow|evenrow')})
        # output container. key = team, value = manager.
        managers = collections.defaultdict(list)
        # each row is a manager.
        for row in rows:
            tds = [item.getText().strip() for item in row.findAll('td')]
            manager = utils.str.normalizeWhitespace(tds[0])
            exp = tds[1]
            record = tds[2]
            team = tds[3]  # translate it into our abbreviation below.
            team = self._translateTeam('team', 'fulltrans', team)
            managers[team] = "{0} :: Manager is {1}({2}) with {3} years experience.".format(self._red(team), self._bold(manager), record, exp)
        # output time.
        output = managers.get(optteam)
        if not output:  # something broke if we didn't find them.
            irc.reply("ERROR: Something went horribly wrong looking up the manager for: {0}".format(optteam))
        else:  # we found so output.
            irc.reply(output)

    mlbmanager = wrap(mlbmanager, [('somethingWithoutSpaces')])

    def mlbstandings(self, irc, msg, args, optlist, optdiv):
        """[--full|--expanded|--vsdivision] <ALE|ALC|ALW|NLE|NLC|NLW>
        Display divisional standings for a division.
        Use --full or --expanded or --vsdivision to show extended stats.
        Ex: --full ALC or --expanded ALE.
        """

        # first, check getopts for what to display.
        full, expanded, vsdivision = False, False, False
        for (option, arg) in optlist:
            if option == 'full':
                full = True
            if option == 'expanded':
                expanded = True
            if option == 'vsdivision':
                vsdivision = True
        # now check optdiv for the division.
        optdiv = optdiv.upper() # lower to match keys. values are in the table to match with the html.
        leaguetable =   {'ALE': 'American League EAST',
                         'ALC': 'American League CENTRAL',
                         'ALW': 'American League WEST',
                         'NLE': 'National League EAST',
                         'NLC': 'National League CENTRAL',
                         'NLW': 'National League WEST' }
        if optdiv not in leaguetable:  # make sure keys are present.
            irc.reply("ERROR: League must be one of: {0}".format(" | ".join(sorted(leaguetable.keys()))))
            return

        # build and fetch url. diff urls depending on option.
        if expanded:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3MvXy90eXBlL2V4cGFuZGVk')
        elif vsdivision:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3MvXy90eXBlL3ZzLWRpdmlzaW9u')
        else:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3M=')
        # now fetch url.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8') # one of these below will break if formatting changes.
        div = soup.find('div', attrs={'class':'mod-container mod-table mod-no-header'}) # div has all
        table = div.find('table', attrs={'class':'tablehead'}) # table in there
        rows = table.findAll('tr', attrs={'class':re.compile('^oddrow.*?|^evenrow.*?')}) # rows are each team
        # list to hold our defaultdicts.
        object_list = []
        lengthlist = collections.defaultdict(list)  # sep data structure to determine length.
        # each row is something in the standings.
        for row in rows:
            league = row.findPrevious('tr', attrs={'class':'stathead'})
            header = row.findPrevious('tr', attrs={'class':'colhead'}).findAll('td')
            tds = row.findAll('td')
            # we shove each row (team) into an OD.
            d = collections.OrderedDict()
            division = "{0} {1}".format(league.getText(), header[0].getText())
            # only inject what we need
            if division == leaguetable[optdiv]: # from table above. only match what we need.
                for i, td in enumerate(tds):
                    if i == 0: # manual replace of team here because the column doesn't say team.
                        d['TEAM'] = tds[0].getText()
                        lengthlist['TEAM'].append(len(tds[0].getText()))
                    else:
                        d[header[i].getText()] = td.getText().replace('  ',' ') # add to ordereddict + conv multispace to one.
                        lengthlist[header[i].getText()].append(len(td.getText())) # add key based on header, length of string.
                object_list.append(d)  # append OD to list.
        # partial sanity check but more of a cheap copy because of how we output.
        if len(object_list) > 0:
            object_list.insert(0,object_list[0])  # copy first item again.
        else:  # bailout if something broke but most likely did above.
            irc.reply("ERROR: Something broke returning mlbstandings.")
            return
        # now prepare to output.
        if not full and not expanded and not vsdivision:  # display short.
            divstandings = []  # list for output.
            for i, each in enumerate(object_list[1:]):  # skip the first since its the header. iterate through to format+append.
                divstr = "#{0} {1} {2}-{3} {4}gb".format(i+1, self._bold(each['TEAM']), each['W'], each['L'], each['GB'])
                divstandings.append(divstr)  # append.
            # now output the short.
            irc.reply("{0} standings :: {1}".format(self._red(optdiv), " | ".join(divstandings)))
        else:  # display full rankings.
            for i, each in enumerate(object_list):
                if i == 0:  # to print the duplicate but only output the header of the table.
                    headerOut = ""
                    for keys in each.keys():  # only keys on the first list entry, a dummy/clone.
                        headerOut += "{0:{1}}".format(self._ul(keys), max(lengthlist[keys])+4, key=int)  # normal +2 but bold eats up +2 more, so +4.
                    irc.reply(headerOut)  # output header.
                else:  # print the division now.
                    tableRow = ""  # empty string we += to with each "row".
                    for inum, k in enumerate(each.keys()):
                        if inum == 0:  # team here, which we want to bold.
                            tableRow += "{0:{1}}".format(self._bold(each[k]),max(lengthlist[k])+4, key=int)  #+4 since bold eats +2.
                        else:  # rest of the elements outside the team.
                            tableRow += "{0:{1}}".format(each[k],max(lengthlist[k])+2, key=int)
                    irc.reply(tableRow)  # output.

    mlbstandings = wrap(mlbstandings, [getopts({'full':'', 'expanded':'', 'vsdivision':''}), ('somethingWithoutSpaces')])

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
        div1 = soup.find('div', attrs={'id':'content'})
        div2 = div1.find('div', attrs={'class':'lineup'})
        divs = div2.findAll('div')
        # each div has different information and must be processed differently.
        firstdiv = divs[0]  # home pitcher.
        #starttime = firstdiv.find('b').getText()
        #teampitcher = firstdiv.find('a').getText()
        seconddiv = divs[1]   # opp pitcher.
        atvs = seconddiv.find('b').getText(separator=' ')
        otherpitcher = seconddiv.findAll('a')[1].getText()
        thirddiv = divs[2]  # lineups.
        lineup = thirddiv.findAll('div')
        # prepare to output.
        lineup = " | ".join([i.getText(separator=' ').encode('utf-8') for i in lineup])
        irc.reply("{0} LINEUP :: ({1}, {2}) :: {3}".format(self._red(optteam), atvs, otherpitcher, lineup))

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
            irc.reply("{0:27} {1:9} {2:<10} {3:<15} {4:<15}".format("NAME","STATUS","DATE","INJURY","RETURNS"))
            for inj in object_list:  # one per line since we are detailed.
                irc.reply("{0:<27} {1:<9} {2:<10} {3:<15} {4:<15}".format(inj['name'], inj['status'], inj['date'], inj['injury'], inj['returns']))
        else:  # no detail.
            irc.reply("{0} :: {1} Injuries".format(self._red(optteam), len(object_list)))
            irc.reply(" | ".join([item['name'] + " (" + item['returns'] + ")" for item in object_list]))

    mlbinjury = wrap(mlbinjury, [getopts({'details':''}), ('somethingWithoutSpaces')])

    def mlbpowerrankings(self, irc, msg, args):
        """
        Display this week's MLB Power Rankings.
        """

        # build and fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9wb3dlcnJhbmtpbmdz')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process HTML
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        if not soup.find('table', attrs={'class':'tablehead'}):
            irc.reply("Something broke heavily formatting on powerrankings page.")
            return
        # go about regular html business.
        datehead = soup.find('div', attrs={'class':'date floatleft'}).getText()
        table = soup.find('table', attrs={'class':'tablehead'})
        headline = table.find('tr', attrs={'class':'stathead'})
        rows = table.findAll('tr', attrs={'class':re.compile('^oddrow|^evenrow')})
        # list for each team.
        powerrankings = []
        # each row is a team.
        for row in rows: # one row per team.
            tds = row.findAll('td') # findall tds.
            rank = tds[0].getText() # rank number.
            team = tds[1].find('div', attrs={'style':'padding:10px 0;'}).find('a').getText() # finds short.
            lastweek = tds[2].find('span', attrs={'class':'pr-last'}).getText()
            lastweek = lastweek.replace('Last Week:', '').strip() # rank #
            # check if we're up or down and insert a symbol.
            if int(rank) < int(lastweek):
                symbol = self._green('▲')
            elif int(rank) > int(lastweek):
                symbol = self._red('▼')
            else: # - if the same.
                symbol = "-"
            # now add the rows to our data structures.
            powerrankings.append("{0}. {1} (prev: {2} {3})".format(rank, team, symbol, lastweek))
        # now output. conditional if we have the team or not.
        irc.reply("{0}".format(self._blue(headline.getText()), self._bold(datehead)))
        for N in self._batch(powerrankings, 12): # iterate through each team. 12 per line
            irc.reply("{0}".format(" | ".join([item for item in N])))

    mlbpowerrankings = wrap(mlbpowerrankings)

    def mlbteamleaders(self, irc, msg, args, optteam, optcategory):
        """<team> <category>
        Display leaders on a team in stats for a specific category.
        Ex. NYY hr or LAD ops
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # now test out for valid category.
        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'r':'runs', 'ab':'atBats', 'obp':'onBasePct',
                    'slug':'slugAvg', 'ops':'OPS', 'sb':'stolenBases', 'runscreated':'runsCreated',
                    'w': 'wins', 'l': 'losses', 'win%': 'winPct', 'era': 'ERA',  'k': 'strikeouts',
                    'k/9ip': 'strikeoutsPerNineInnings', 'holds': 'holds', 's': 'saves',
                    'gp': 'gamesPlayed', 'cg': 'completeGames', 'qs': 'qualityStarts', 'whip': 'WHIP' }
        optcategory = optcategory.lower()
        if optcategory not in category:
            irc.reply("ERROR: Category must be one of: {0}".format(" | ".join(sorted(category.keys()))))
            return
        # build and fetch url.
        lookupteam = self._translateTeam('eid', 'team', optteam)
        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RlYW1zdGF0cw==') + '?teamId=%s&lang=EN&category=%s&y=1&wjb=' % (lookupteam, category[optcategory])
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        table = soup.find('table', attrs={'class':'table'})
        rows = table.findAll('tr')[1:6]  # top 5 only.
        # list for output.
        object_list = []
        # grab the first five and go.
        for row in rows:  # rank, player, stat
            tds = [item.getText().strip() for item in row.findAll('td')]
            object_list.append("{0}. {1} {2}".format(tds[0], tds[1], tds[2]))
        # prepare output and output.
        thelist = " | ".join([item for item in object_list])
        irc.reply("{0} leaders for {1} :: {2}".format(self._red(optteam), self._bold(optcategory.upper()), thelist))

    mlbteamleaders = wrap(mlbteamleaders, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbleagueleaders(self, irc, msg, args, optleague, optcategory):
        """<MLB|AL|NL> <category>
        Display top 10 teams in category for a specific stat.
        Categories: hr, avg, rbi, ra, sb, era, whip, k
        Ex: MLB hr or AL rbi or NL era
        """

        # establish valid leagues and valid categories.
        league = {'mlb': '9', 'al':'7', 'nl':'8'}  # do our own translation here for league/category.
        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'ra':'runs', 'sb':'stolenBases', 'era':'ERA', 'whip':'whip', 'k':'strikeoutsPerNineInnings'}
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
        table = soup.find('table', attrs={'class':'table'})
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

    def mlbteamtrans(self, irc, msg, args, optteam):
        """<team>
        Shows recent MLB transactions for a team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if not optteam:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # build and fetch url.
        lookupteam = self._translateTeam('eid', 'team', optteam)
        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RlYW10cmFuc2FjdGlvbnM=') + '?teamId=%s&wjb=' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        t1 = soup.findAll('div', attrs={'class':re.compile('ind|ind tL|ind alt')})
        # sanity check.
        if len(t1) < 1:
            irc.reply("ERROR: No transactions found for: {0}".format(optteam))
            return
        else:  # we found transactions.
            for item in t1:
                if "href=" not in str(item):
                    trans = item.findAll(text=True)
                    irc.reply("{0:8} {1}".format(self._bold(trans[0]), trans[1]))

    mlbteamtrans = wrap(mlbteamtrans, [('somethingWithoutSpaces')])

    def mlbtrans(self, irc, msg, args, optdate):
        """[YYYYmmDD]
        Display all mlb transactions. Will only display today's.
        Use date in format: 20120912 to display other dates.
        Ex: 20130525.
        """

        # do we have a date or not?
        if optdate:  # if we have a date, test it out if it's valid.
            try:
                datetime.datetime.strptime(optdate, '%Y%m%d')
            except:  # invalid date.
                irc.reply("ERROR: Date format must be in YYYYMMDD. Ex: 20120714")
                return
        else:  # no date so get "today
            optdate = datetime.datetime.now().strftime("%Y%m%d")
        # build and fetch url.
        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RyYW5zYWN0aW9ucz93amI9') + '&date=%s' % optdate
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # sanity check on the html.
        if "No transactions today." in html:
            irc.reply("ERROR: No transactions for: {0}".format(optdate))
            return
        # if we do have transactions, process HTML.
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
        t1 = soup.findAll('div', attrs={'class':re.compile('ind alt|ind')})

        if len(t1) < 1:  # nothing found.
            irc.reply("ERROR: I did not find any MLB transactions for: {0}".format(optdate))
            return
        else:  # we have transactions on the date.
            irc.reply("Displaying all MLB transactions for: {0}".format(self._red(optdate)))
            for trans in t1:
                if "<a href=" not in trans:  # no links (eliminates headers.)
                    match1 = re.search(r'<b>(.*?)</b><br />(.*?)</div>', str(trans), re.I|re.S)  # strip out team and transaction.
                    if match1:
                        team = match1.group(1)  # shorten here?
                        transaction = match1.group(2)
                        irc.reply("{0} - {1}".format(self._bold(team), transaction))

    mlbtrans = wrap(mlbtrans, [optional('somethingWithoutSpaces')])

    def mlbprob(self, irc, msg, args, optteam):
        """<TEAM>
        Display the MLB probables for a team over the next 5 stars.
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
            html = html.replace('WAS','WSH').replace('CHW','CWS').replace('KAN','KC').replace('TAM','TB').replace('SFO','SF').replace('SDG','SD')
            # process html.
            soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES, fromEncoding='utf-8')
            rows = soup.findAll('div', attrs={'class':re.compile('ind alt tL spaced|ind tL spaced')})
            # each row is a game that day.
            for row in rows:  # we grab the matchup (text) to match. the rest goes into a dict.
                textmatch = re.search(r'<a class="bold inline".*?<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)$', row.renderContents(), re.I|re.S|re.M)
                if textmatch:  # only inject if we match
                    d = {}
                    d['date'] = eachdate  #  text from above. use BS for matchup and regex for the rest.
                    d['matchup'] = row.find('a', attrs={'class': 'bold inline'}).getText().strip()
                    d['vteam'] = textmatch.group(1).strip().replace(':','')
                    d['vpitcher'] = textmatch.group(2).strip()
                    d['vpstats'] = textmatch.group(3).strip()
                    d['hteam'] = textmatch.group(4).strip().replace(':','')
                    d['hpitcher'] = textmatch.group(5).strip()
                    d['hpstats'] = textmatch.group(6).strip()
                    probables.append(d)  # order preserved via list. we add the dict.
        # now lets output.
        for eachentry in probables:  # iterate through list and only output when team is matched.
            if optteam in eachentry['matchup']:  # if optteam is contained in matchup, we output.
                irc.reply("{0:10} {1:25} {2:4} {3:15} {4:15} {5:4} {6:15} {7:15}".format(eachentry['date'], eachentry['matchup'],\
                    eachentry['vteam'], eachentry['vpitcher'],eachentry['vpstats'], eachentry['hteam'], eachentry['hpitcher'], eachentry['hpstats']))

    mlbprob = wrap(mlbprob, [('somethingWithoutSpaces')])

Class = MLB


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=250:
