# -*- coding: utf-8 -*-
##
# Copyright (c) 2012-2013, spline
# All rights reserved.
#
#
###

from BeautifulSoup import BeautifulSoup
import urllib2
import re
import collections
import datetime
import random
import sqlite3
from itertools import groupby, count
import os
import json

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

    def _httpget(self, url, h=None, d=None):
        """General HTTP resource fetcher. Supports b64encoded urls."""

        if not url.startswith('http://'):
            url = self._b64decode(url)

        self.log.info(url)

        try:
            if h and d:
                page = utils.web.getUrl(url, headers=h, data=d)
            else:
                page = utils.web.getUrl(url)
            return page
        except utils.web.Error as e:
            self.log.error("I could not open {0} error: {1}".format(url,e))
            return None

    def _shortenUrl(self, url):
        """Shortens a long URL into a short one."""

        try:
            posturi = "https://www.googleapis.com/urlshortener/v1/url"
            data = json.dumps({'longUrl' : url})
            request = urllib2.Request(posturi, data, {'Content-Type':'application/json'})
            response = urllib2.urlopen(request)
            return json.loads(response.read())['id']
        except:
            return url

    def _b64decode(self, string):
        """Returns base64 decoded string."""

        import base64
        return base64.b64decode(string)

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
            query = "select team from mlb"
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
            query = "select team from mlbteamaliases where teamalias LIKE ?"  # check aliases first.
            cursor.execute(query, ('%'+optteam.lower()+'%',))
            aliasrow = cursor.fetchone()  # this will be None or the team (NYY).
            if not aliasrow:  # person looking for team.
                query = "select team from mlb where team=?"
                cursor.execute(query, (optteam.upper(),))  # standard lookup. go upper. nyy->NYY.
                teamrow = cursor.fetchone()
                if not teamrow:  # team is not found. Error.
                    returnval = 1  # checked in each command.
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
            query = "select %s from mlb where %s='%s'" % (db, column, optteam)
            cursor.execute(query)
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

    def mlbpitcher(self, irc, msg, args, optteam):
        """<TEAM>
        Displays current pitcher(s) in game for a specific team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
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
        soup = BeautifulSoup(html)
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
            self.log.info("ERROR: I got {0} as a team. I only have: {1}".format(optteam, str(teamdict)))
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
            soup = BeautifulSoup(html)
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

        testdate = self._validate(optyear, '%Y')
        if not testdate:
            irc.reply("ERROR: Invalid year. Must be YYYY.")
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi93b3JsZHNlcmllcy9oaXN0b3J5L3dpbm5lcnM=')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class': re.compile('^evenrow|^oddrow')})
        worldseries = collections.defaultdict(list)

        for row in rows:
            tds = row.findAll('td')
            year = tds[0]
            winner = tds[1].getText()
            loser = tds[2].getText()
            series = tds[3].getText()
            appendString = str("Winner: " + " ".join(winner.split()) + "  Loser: " + " ".join(loser.split()) + "  Series: " + " ".join(series.split()))
            worldseries[str(year.getText())].append(appendString)

        outyear = worldseries.get(optyear, None)

        if not outyear:
            irc.reply("ERROR: I could not find MLB World Series information for: %s" % optyear)
            return
        else:
            output = "{0} World Series :: {1}".format(self._bold(optyear), "".join(outyear))
            irc.reply(output)

    mlbworldseries = wrap(mlbworldseries, [('somethingWithoutSpaces')])

    def mlballstargame(self, irc, msg, args, optyear):
        """<YYYY>
        Display results for that year's MLB All-Star Game. Ex: 1996. Earliest year is 1933 and latest is this season.
        """

        testdate = self._validate(optyear, '%Y')
        if not testdate:
            irc.reply("ERROR: Invalid year. Must be YYYY.")
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9hbGxzdGFyZ2FtZS9oaXN0b3J5')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class': re.compile('^evenrow|^oddrow')})

        allstargames = collections.defaultdict(list)

        for row in rows:
            tds = row.findAll('td')
            year, score, location, attendance, mvp = tds[0], tds[1], tds[2], tds[4], tds[3]
            appendString = str("Score: " + score.getText() + "  Location: " + location.getText() + "  Attendance: " + attendance.getText() + "  MVP: " + mvp.getText())
            allstargames[str(year.getText())].append(appendString)

        outyear = allstargames.get(optyear, None)

        if not outyear:
            irc.reply("ERROR: I could not find MLB All-Star Game information for: %s" % optyear)
            return
        else:
            output = "{0} All-Star Game :: {1}".format(self._bold(optyear), "".join(outyear))
            irc.reply(output)

    mlballstargame = wrap(mlballstargame, [('somethingWithoutSpaces')])

    def mlbcyyoung(self, irc, msg, args):
        """
        Display Cy Young prediction list. Uses a method, based on past results, to predict Cy Young balloting.
        """

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9mZWF0dXJlcy9jeXlvdW5n')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # stupid HTML replace requirement.
        html = html.replace('&amp;','&').replace('ARZ','ARI').replace('CHW','CWS').replace('WAS','WSH').replace('MLW','MIL')
        # now process HTML.
        soup = BeautifulSoup(html)
        players = soup.findAll('tr', attrs={'class': re.compile('(^oddrow.*?|^evenrow.*?)')})

        cyyoung = collections.defaultdict(list)

        for player in players:
            colhead = player.findPrevious('tr', attrs={'class':'stathead'})
            rank = player.find('td')
            playerName = rank.findNext('td')
            team = playerName.findNext('td')
            appendString = str(rank.getText() + ". " + ircutils.bold(playerName.getText()) + " (" + team.getText() + ")")
            cyyoung[str(colhead.getText())].append(appendString)

        for i,x in cyyoung.iteritems():
            descstring = " | ".join([item for item in x])
            output = "{0} :: {1}".format(self._red(i), descstring)
            irc.reply(output)

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

        twoteams = random.sample(teams, 2)  # grab the two, randomly.
        twoteamplayers = collections.defaultdict()  # setup defaultdict for team = key, values = players

        for pickTeam in twoteams:
            # create url and fetch
            url = self._b64decode('aHR0cDovL3Nwb3J0cy55YWhvby5jb20vbWxiL3RlYW1z') + '/%s/roster' % pickTeam
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
            # now process the html.
            soup = BeautifulSoup(html)
            bbteam = soup.find('div', attrs={'class':'info'}).find('h1', attrs={'itemprop':'name'})
            #div = soup.find('div', attrs={'id':'team-roster'})  # roster div
            rows = soup.findAll('th', attrs={'class':'title', 'scope':'row'})
            # each row is a player.
            for row in rows:
                player = row.getText()
                playersplit = player.split(',', 1)  # split on last, first so we can reverse below.
                p1 = playersplit[1].strip().encode('utf-8')
                p2 = playersplit[0].strip().encode('utf-8')
                player = "{0} {1}".format(p1, p2)
                twoteamplayers.setdefault(bbteam.getText(), []).append(player)  # append.

        # now we need to pick the player(s)
        outlist = []  # list will store: 0. team 1. players 2. team 3. players.

        for x, y in twoteamplayers.iteritems():
            randnum = random.randint(1, 3)  # number of players. 1-3
            randplayers = random.sample(y, randnum)  # use to randomly fetch players.
            outlist.append(x)  # append team.
            outlist.append(" and ".join(randplayers))  # append player(s)

        # finally, output.
        output = "{0} :: The {1} trade {2} to the {3} for {4}".format(self._red("MLB TRADE MACHINE"),\
                self._bu(outlist[0]), self._bold(outlist[1]), self._bu(outlist[2]), self._bold(outlist[3]))
        irc.reply(output)

    mlbtrademachine = wrap(mlbtrademachine)

    def mlbheadtohead(self, irc, msg, args, optteam, optopp):
        """<team> <opp>
        Display the record between two teams head-to-head. EX: NYY BOS
        Ex: NYY BOS
        """

        # first test for similarity.
        if optteam == optopp:
            irc.reply("ERROR: You must specify two different teams.")
            return
        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # test for valid teams.
        optopp = self._validteams(optopp)
        if optopp is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3MvZ3JpZA==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # process html.
        html = html.replace('CHW', 'CWS')  # mangle this since.. it's there'
        soup = BeautifulSoup(html)
        tables = soup.findAll('table', attrs={'class':'tablehead'})  # two tables.

        headToHead = collections.defaultdict(list)

        for table in tables:
            rows = table.findAll('tr', attrs={'class':re.compile('^oddrow.*?|^evenrow.*?')})
            for i,row in enumerate(rows):  # each rows now.
                header = row.findPrevious('tr', attrs={'class':'colhead'}).findAll('td')
                team = row.findAll('td')[0]
                tds = row.findAll('td')[1:]
                for j,td in enumerate(tds):
                    keyString = str(team.getText() + header[j+1].getText())  # key using team+header[j] text since vs. is in it. +1 due to tds being moved [1:]
                    headToHead[keyString].append(str(td.getText()))

        output = headToHead.get(str(optteam + "vs." + optopp), None)  # need to format w/ vs. here to match the key.

        if output:
            if output is not "--":
                recordSplit = "".join(output).split('-')
                win, loss = recordSplit[0], recordSplit[1]  # It is defined as wins divided by wins plus losses (i.e. — the total number of matches)
                if win.isdigit() and loss.isdigit():
                    if win == "0" and loss == "0":  # this prevents division by 0.
                        percentage = "0.0"
                    else:  # we don't have both zeros.
                        percentage = ("%.3f" % (float(win) / float(int(win)+int(loss))))  # win percentage, limit to 3 precision
                    irc.reply("Head-to-head record :: {0} vs. {1} :: {2} ({3})".format(self._bold(optteam), ircutils.bold(optopp), "".join(output), percentage))
                else:
                    irc.reply("Head-to-head record :: {0} vs. {1} :: {2}".format(self._bold(optteam), self._bold(optopp), "".join(output)))
            else:
                irc.reply("Head-to-head record :: {0} vs. {1} :: {2}".format(self._bold(optteam), self._bold(optopp), "".join(output)))
        else:
            irc.reply("Head-to-head record not found for {0} vs. {1}".format(self._bold(optteam), self._bold(optopp)))

    mlbheadtohead = wrap(mlbheadtohead, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbseries(self, irc, msg, args, optteam, optopp):
        """<team> <opp>
        Display the remaining games between TEAM and OPP in the current schedule.
        Ex: NYY TOR
        """

        # for the url and later.
        currentYear = str(datetime.date.today().year)

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # test for valid teams.
        optopp = self._validteams(optopp)
        if optopp is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtcy9wcmludFNjaGVkdWxlL18vdGVhbQ==') + '/%s/season/%s' % (optteam, currentYear)
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)  # the html here is junk/garbage. soup cleans this up, even if using a regex.

        append_list, out_list = [], []

        schedRegex = '<tr><td><font class="verdana" size="1"><b>(.*?)</b></font></td><td><font class="verdana" size="1">(.*?)</font></td>.*?<td align="right"><font class="verdana" size="1">(.*?)</font></td></tr>'

        patt = re.compile(schedRegex, re.I|re.S|re.M)  # ugh, regex was the only way due to how horrible the printSchedule is.

        for m in patt.finditer(str(soup)):
            mDate, mOpp, mTime = m.groups()
            mDate = mDate.replace('.', '').replace('Sept', 'Sep')  # replace the at and Sept has to be fixed for %b
            if "at " in mOpp:  # clean-up the opp and shorten.
                mOpp = self._translateTeam('team', 'ename', mOpp.replace('at ', '').strip())
                mOpp = "@" + mOpp
            else:
                mOpp = self._translateTeam('team', 'ename', mOpp.strip())
            if datetime.datetime.strptime(mDate + " " + currentYear, '%b %d %Y').date() >= datetime.date.today():  # only show what's after today
                append_list.append(mDate + " - " + self._bold(mOpp) + " " + mTime)

        for each in append_list: # here, we go through all remaining games, only pick the ones with the opp in it, and go from there.
            if optopp in each: # this is real cheap using string matching instead of assigning keys, but easier.
                out_list.append(each)

        if len(out_list) > 0:
            descstring = " | ".join([item for item in out_list])
            output = "There are {0} games remaining between {1} and {2} :: {3}".format(self._red(len(out_list)), self._bold(optteam), self._bold(optopp), descstring)
            irc.reply(output)
        else:
            irc.reply("I do not see any remaining games between: {0} and {1} in the {2} schedule.".format(self._bold(optteam), self._bold(optopp), currentYear))

    mlbseries = wrap(mlbseries, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbejections(self, irc, msg, args):
        """
        Display the total number of ejections and five most recent for the MLB season.
        """

        url = self._b64decode('aHR0cDovL3BvcnRhbC5jbG9zZWNhbGxzcG9ydHMuY29tL2hpc3RvcmljYWwtZGF0YS8=') + str(datetime.datetime.now().year) + '-mlb-ejection-list'
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        ejectedTitle = soup.find('span', attrs={'id':'sites-page-title'}).getText()
        ejectedTotal = soup.find('div', attrs={'class':'sites-list-showing-items'}).find('span').getText()
        table = soup.find('table', attrs={'id':'goog-ws-list-table', 'class':'sites-table goog-ws-list-table'})
        rows = table.findAll('tr')[1:6]  # last 5. header row is 0.

        append_list = []

        for row in rows:
            tds = row.findAll('td')
            date = tds[0].getText()
            umpname = tds[4].getText()
            ejteam = tds[5].getText()
            #ejpos = tds[6].getText()
            ejected = tds[7].getText()
            date = self._dtFormat('%m/%d', date, '%B %d, %Y') # March 27, 2013
            append_list.append("{0} - {1} ejected {2} ({3})".format(date, umpname, ejected, ejteam))

        irc.reply("{0} :: {1} ejections this season.".format(self._bold(ejectedTitle), self._red(ejectedTotal)))
        irc.reply(" | ".join([item for item in append_list]))

    mlbejections = wrap(mlbejections)

    def mlbarrests(self, irc, msg, args):
        """
        Display the last 5 MLB arrests.
        """

        url = self._b64decode('aHR0cDovL2FycmVzdG5hdGlvbi5jb20vY2F0ZWdvcnkvcHJvLWJhc2ViYWxsLw==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        html = html.replace('&nbsp;', ' ').replace('&#8217;', '’')

        soup = BeautifulSoup(html)
        lastDate = soup.findAll('span', attrs={'class': 'time'})[0]
        divs = soup.findAll('div', attrs={'class': 'entry'})

        arrestlist = []

        for div in divs:
            title = div.find('h2').getText().encode('utf-8')
            datet = div.find('span', attrs={'class': 'time'}).getText().encode('utf-8')
            datet = self._dtFormat("%m/%d", datet, "%B %d, %Y") # translate date.
            arrestedfor = div.find('strong', text=re.compile('Team:'))
            if arrestedfor:
                matches = re.search(r'<strong>Team:.*?</strong>(.*?)<br />', arrestedfor.findParent('p').renderContents(), re.I| re.S| re.M)
                if matches:
                    college = matches.group(1).replace('(NFL)','').encode('utf-8').strip()
                else:
                    college = "None"
            else:
                college = "None"
            arrestlist.append("{0} :: {1} - {2}".format(datet, title, college))

        # date math.
        a = datetime.date.today()
        b = datetime.datetime.strptime(str(lastDate.getText()), "%B %d, %Y")
        b = b.date()
        delta = b - a
        daysSince = abs(delta.days)

        # output
        irc.reply("{0} days since last MLB arrest".format(self._red(daysSince)))
        for each in arrestlist[0:6]:
            irc.reply(each)

    mlbarrests = wrap(mlbarrests)

    def mlbstats(self, irc, msg, args, optlist, optplayer):
        """<--year YYYY> [player name]
        Display career totals and season averages for player. If --year YYYY is
        specified, it will display the season stats for that player, if available.
        NOTE: This command is intended for retired/inactive players, not active ones.
        """

        (first, last) = optplayer.split(" ", 1)  # playername needs to be "first-last".
        searchplayer = first + '-' + last  # reconstruct here.

        optyear = False
        for (option, arg) in optlist:
            if option == 'year':
                optyear = arg

        url = self._b64decode('aHR0cDovL3NlYXJjaC5lc3BuLmdvLmNvbS8=') + '%s' % searchplayer
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # first parse the searchpage.
        soup = BeautifulSoup(html)
        if not soup.find('li', attrs={'class':'result mod-smart-card'}):
            irc.reply("ERROR: I didn't find a link for: {0}. Perhaps you should be more specific and give a full playername".format(optplayer))
            return
        else:
            playercard = soup.find('li', attrs={'class':'result mod-smart-card'})
        # for the rare occurences, check the url.
        if 'http://espn.go.com/mlb/players/stats?playerId=' not in playercard.renderContents():
            irc.reply("ERROR: Could not find a link to career stats for: {0}".format(optplayer))
            return
        else:  # need the link so we can follow.
            url = playercard.find('a', attrs={'href':re.compile('.*?espn.go.com/mlb/players/stats.*?')})['href']
        # make sure we have the link and fetch.
        if not url:
            irc.reply("ERROR: I didn't find the link I needed for career stats. Did something break?")
            return
        else:
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
        # now parse the player's career page.
        soup = BeautifulSoup(html)
        playerName = soup.find('div', attrs={'class':'player-bio'}).find('h1').getText()  # playerName.
        table = soup.find('table', attrs={'class':'tablehead'}) # everything stems from the table.
        header = table.find('tr', attrs={'class':'colhead'}).findAll('td') # columns to reference.

        if optyear:
            seasonrows = table.findAll('tr', attrs={'class':re.compile('^oddrow$|^evenrow$')}) # find all outside the season+totals
            season_data = collections.defaultdict(list) # key will be the year.

            for row in seasonrows:
                tds = row.findAll('td')
                for i, td in enumerate(tds):
                    season_data[str(tds[0].getText())].append("{0}: {1}".format(self._bold(header[i].getText()), td.getText()))

            outyear = season_data.get(str(optyear), None)

            if not outyear:
                irc.reply("ERROR: No stats found for {0} in {1}".format(playerName, optyear))
            else:
                outyear = " | ".join([item for item in outyear])
                irc.reply("{0} :: {1}".format(playerName, outyear))
        else:  # career stats not for a specific year.
            endrows = table.findAll('tr', attrs={'class':re.compile('^evenrow bi$|^oddrow bi$')})

            for total in endrows:
                if total.find('td', text="Total"):
                    totals = total.findAll('td')
                if total.find('td', text="Season Averages"):
                    seasonaverages = total.findAll('td')
            #remove the first td, but match up header via j+2
            del seasonaverages[0]
            del totals[0:2]
            # do the averages for output.
            seasonstring = " | ".join([self._bold(header[i+2].getText()) + ": " + td.getText() for i,td in enumerate(seasonaverages)])
            totalstring = " | ".join([self._bold(header[i+2].getText()) + ": " + td.getText() for i,td in enumerate(totals)])
            # output time.
            irc.reply("{0} Season Averages :: {1}".format(self._red(playerName), seasonstring))
            irc.reply("{0} Career Totals :: {1}".format(self._red(playerName), totalstring))

    mlbstats = wrap(mlbstats, [(getopts({'year':('int')})), ('text')])

    def mlbgamesbypos (self, irc, msg, args, optteam):
        """<team>
        Display a team's games by position. Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # didn't want a new table here for one site, so this is a cheap stop-gap. must do this for urls.
        if optteam == 'CWS':
            optteam = 'chw'
        else:
            optteam = optteam.lower()

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL2xpbmV1cC9fL25hbWU=') + '/%s/' % optteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)

        table = soup.find('td', attrs={'colspan':'2'}, text="GAMES BY POSITION").findParent('table')
        rows = table.findAll('tr', attrs={'class':re.compile('oddrow|evenrow')})

        append_list = []

        for row in rows:
            playerPos = row.find('td').find('strong')
            playersList = playerPos.findNext('td')
            append_list.append("{0} {1}".format(self._bold(playerPos.getText()), playersList.getText()))

        descstring = " | ".join([item for item in append_list])
        output = "{0} (games by POS) :: {1}".format(self._red(optteam.upper()), descstring)

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
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        active, fortyman = True, False
        for (option, arg) in optlist:
            if option == 'active':
                active, fortyman = True, False
            if option == '40man':
                active, fortyman = False, True
        # didn't want a new table here for one site, so this is a cheap stop-gap. must do this for urls.
        if optteam == 'CWS':
            optteam = 'chw'
        else:
            optteam = optteam.lower()

        if active and not fortyman:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL3Jvc3Rlci9fL25hbWU=') + '/%s/type/active/' % optteam
        else:  # 40man
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL3Jvc3Rlci9fL25hbWU=') + '/%s/' % optteam

        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        table = soup.find('div', attrs={'class':'mod-content'}).find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr', attrs={'class':re.compile('^oddrow player.*|^evenrow player.*')})

        team_data = collections.defaultdict(list)

        for row in rows:
            playerType = row.findPrevious('tr', attrs={'class':'stathead'})
            playerNum = row.find('td')
            playerName = playerNum.findNext('td').find('a')
            playerPos = playerName.findNext('td')
            team_data[str(playerType.getText())].append("{0} ({1})".format(playerName.getText(), playerPos.getText()))

        # output time.
        for i, j in team_data.iteritems():
            output = "{0} {1} :: {2}".format(self._red(optteam.upper()), self._bold(i), " | ".join([item for item in j]))
            irc.reply(output)

    mlbroster = wrap(mlbroster, [getopts({'active':'','40man':''}), ('somethingWithoutSpaces')])

    def mlbrosterstats(self, irc, msg, args, optteam):
        """[team]
        Displays top 5 youngest/oldest teams.
        Optionally, use TEAM as argument to display roster stats/averages for MLB team. Ex: NYY
        """

        if optteam:  # if we want a specific team, validate it.
            optteam = self._validteams(optteam)
            if optteam is 1:  # team is not found in aliases or validteams.
                irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
                return
        # fetch url.
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy9yb3N0ZXJz')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr')[2:]
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

            aString = "RHB: {0}  LHB: {1}  SH: {2}  RHP: {3}  LHP: {4}  AVG HT: {5}  AVG WEIGHT: {6}  AVG AGE: {7}  YOUNGEST: {8}  OLDEST: {9}".format(\
                        rhb, lhb, sh, rhp, lhp, ht, wt, age, young, old)

            d = collections.OrderedDict()
            d['team'] = str(self._translateTeam('team', 'ename', team))
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

        try: # try and millify.
            figure = self._millify(float(figure))
        except:
            figure = figure

        if negative:
            figure = "-" + figure
        # now return
        return figure

    def mlbpayroll(self, irc, msg, args, optteam):
        """<team>
        Display payroll situation for <team>. Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
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

        soup = BeautifulSoup(html)
        teamtitle = soup.find('title')
        tbody = soup.find('tbody')

        payroll = []

        paytds = tbody.findAll('td', attrs={'class':'total team total-title'})
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

    def mlbffplayerratings(self, irc, msg, args, optposition):
        """[position]
        Display MLB player ratings per position. Positions must be one of:
        Batters | Pitchers | C | 1B | 2B | 3B | SS | 2B/SS | 1B/3B | OF | SP | RP
        """

        validpositions = { 'Batters':'?&slotCategoryGroup=1','Pitchers':'?&slotCategoryGroup=2', 'C':'?&slotCategoryId=0', '1B':'?&slotCategoryId=1',
            '2B':'?&slotCategoryId=2', '3B':'?&slotCategoryId=3', 'SS':'?&slotCategoryId=4', '2B/SS':'?&slotCategoryId=6', '1B/3B':'?&slotCategoryId=7',
            'OF':'?&slotCategoryId=5', 'SP':'?&slotCategoryId=14', 'RP':'?&slotCategoryId=15' }

        if optposition and optposition not in validpositions:
            irc.reply("ERROR: Invalid position. Must be one of: %s" % validpositions.keys())
            return

        url = self._b64decode('aHR0cDovL2dhbWVzLmVzcG4uZ28uY29tL2ZsYi9wbGF5ZXJyYXRlcg==')
        if optposition:
            url += '%s' % validpositions[optposition]

        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'id':'playertable_0'})
        rows = table.findAll('tr')[2:12]

        append_list = []

        for row in rows:
            rank = row.find('td')
            player = row.find('td', attrs={'class':'playertablePlayerName'}).find('a')
            rating = row.find('td', attrs={'class':'playertableData sortedCell'})
            append_list.append(rank.getText() + ". " + ircutils.bold(player.getText()) + " (" + rating.getText() + ")")

        # output.
        if optposition:
            title = "Top 10 FF projections at: %s" % optposition
        else:
            title = "Top 10 FF projections"

        output = "{0} :: {1}".format(self._red(title), " | ".join([item for item in append_list]))
        irc.reply(output)

    mlbffplayerratings = wrap(mlbffplayerratings, [optional('somethingWithoutSpaces')])

    def mlbteams(self, irc, msg, args):
        """
        Display a list of valid teams for input.
        """

        irc.reply("Valid MLB teams are: {0}".format(self._allteams()))

    mlbteams = wrap(mlbteams)

    def mlbweather(self, irc, msg, args, optteam):
        """<team>
        Display weather for MLB team at park they are playing at.
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

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
        soup = BeautifulSoup(html)
        h3s = soup.findAll('h3')

        object_list = collections.defaultdict()

        for h3 in h3s:  # each h3 is a game.
            park = h3.find('span', attrs={'style':'float: left;'})
            factor = h3.find('span', attrs={'style': re.compile('color:.*?')})
            matchup = h3.findNext('h4').find('span', attrs={'style':'float: left;'})
            winddir = h3.findNext('img', attrs={'class':'rose'})
            winddir = str(''.join(i for i in winddir['src'] if i.isdigit()))
            windspeed = h3.findNext('p', attrs={'class':'windspeed'}).find('span')
            weather = h3.findNext('h5', attrs={'class':'l'})  #
            if weather.find('img', attrs={'src':'../images/roof.gif'}):
                weather = "[ROOF] " + weather.getText().strip().replace('.Later','. Later').replace('&deg;F','F ')
            else:
                weather = weather.getText().strip().replace('.Later','. Later').replace('&deg;F','F ')

            # now do some split work to get the dict with teams as keys.
            teams = matchup.getText().split(',', 1)  # NYY at DET, 1:05PM ET
            for team in teams[0].split('at'):  # ugly but works.
                object_list[str(team.strip())] = "{0}  at {1}({2})  Weather: {3}  Wind: {4}mph  ({5}deg)".format(\
                    self._ul(matchup.getText()), park.getText(), factor.getText(), weather, windspeed.getText(), winddir)

        output = object_list.get(optteam, None)
        if not output:
            irc.reply("ERROR: No weather found for: %s. Perhaps the team is not playing?" % optteam)
            return
        else:
            irc.reply(output)

    mlbweather = wrap(mlbweather, [('somethingWithoutSpaces')])

    def mlbvaluations(self, irc, msg, args):
        """
        Display current MLB team valuations from Forbes.
        """

        url = self._b64decode('aHR0cDovL3d3dy5mb3JiZXMuY29tL21sYi12YWx1YXRpb25zL2xpc3Qv')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        tbody = soup.find('tbody', attrs={'id':'listbody'})
        rows = tbody.findAll('tr')

        object_list = []

        for row in rows:  # one team per row.
            rank = row.find('td', attrs={'class':'rank'})
            team = rank.findNext('td')
            value = team.findNext('td')
            object_list.append("{0}. {1} {2}M".format(rank.getText(), team.find('h3').getText(), value.getText()))

        # output.
        irc.reply("{0} (in millions):".format(self._red("Current MLB Team Values")))
        irc.reply("{0}".format(" | ".join([item for item in object_list])))

    mlbvaluations = wrap(mlbvaluations)

    def mlbremaining(self, irc, msg, args, optteam):
        """[team]
        Display remaining games/schedule for a playoff contender.
        NOTE: Will only work closer toward the end of the season.
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9odW50Zm9yb2N0b2Jlcg==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        tables = soup.findAll('table', attrs={'class':'tablehead', 'cellpadding':'3', 'cellspacing':'1', 'width':'100%'})

        new_data = collections.defaultdict(list)

        for table in tables:
            team = table.find('tr', attrs={'class':'colhead'}).find('td', attrs={'colspan':'6'})
            gr = table.find('tr', attrs={'class':'oddrow'})
            if team is not None and gr is not None: # horrible and cheap parse
                team = self._translateTeam('team', 'fulltrans', team.getText().title()) # full to short.
                new_data[str(team)].append(gr.getText())

        output = new_data.get(optteam, None)

        if output is None:
            irc.reply("%s not listed. Not considered a playoff contender." % optteam)
        else:
            irc.reply(ircutils.bold(optteam) + " :: " + (" ".join(output)))

    mlbremaining = wrap(mlbremaining, [('somethingWithoutSpaces')])


    def mlbplayoffs(self, irc, msg, args):
        """
        Display playoff matchups if season ended today.
        """

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9odW50Zm9yb2N0b2Jlcg==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        html = html.replace('sdg', 'sd').replace('sfo', 'sf').replace('tam', 'tb').replace('was', 'wsh').replace('kan', 'kc').replace('chw', 'cws')

        soup = BeautifulSoup(html)
        each = soup.findAll('td', attrs={'width':'25%'})

        ol = []

        for ea in each:  # man is this just a horrible stopgap.
            links = ea.findAll('a')
            for link in links:
                linksplit = link['href'].split('/')
                team = linksplit[7]
                ol.append(self._bold(team.upper()))

        if len(ol) != 10:
            irc.reply("ERROR: I did not find playoff matchups. Check closer to playoffs.")
        else:
            irc.reply("Playoffs: AL ({0} vs {1}) vs. {2} | {3} vs. {4} || NL: ({5} vs. {6}) vs. {7} | {8} vs. {9}".format(\
                ol[0], ol[1], ol[2], ol[3], ol[4], ol[5], ol[6], ol[7], ol[8], ol[9]))

    mlbplayoffs = wrap(mlbplayoffs)

    def mlbcareerleaders(self, irc, msg, args, optplayertype, optcategory):
        """<batting|pitching> <category>
        Display career stat leaders in batting|pitching <category>
        Must specify batting or pitching, along with stat from either category.
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

        # be able to not give a category to get them.
        optplayertype = optplayertype.lower()
        if optplayertype == "batting":
            if not optcategory:
                irc.reply("Batting Categories: %s" % battingcategories.keys())
                return
            else:
                optcategory = optcategory.lower()

                if optcategory not in battingcategories:
                    irc.reply("Stat must be one of: %s" % battingcategories.keys())
                    return
                else:
                    endurl = '%s_career.shtml' % battingcategories[optcategory]
        elif optplayertype == "pitching":
            if not optcategory:
                irc.reply("Pitching Categories: %s" % pitchingcategories.keys())
                return
            else:
                optcategory = optcategory.lower()

                if optcategory not in pitchingcategories:
                    irc.reply("Stat must be one of: %s" % pitchingcategories.keys())
                    return
                else:
                    endurl = '%s_career.shtml' % pitchingcategories[optcategory]
        else:
            irc.reply("Must specify batting or pitching.")
            return

        # now fetch url.
        url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2xlYWRlcnMv') + endurl
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # parse.
        soup = BeautifulSoup(html.replace('&nbsp;',' '))
        table = soup.find('table', attrs={'data-crop':'50'})
        rows = table.findAll('tr')

        object_list = []

        # header row = first, 1-10.
        for row in rows[1:11]:
            rank = row.find('td', attrs={'align':'right'})
            player = rank.findNext('td')
            stat = player.findNext('td')
            if player.find('strong'):
                player = self._ul(player.find('a').find('strong').getText().strip())
            else:
                player = player.find('a').getText()
            object_list.append("{0} {1} ({2})".format(rank.getText(), self._bold(player), stat.getText()))

        # output time.
        output = self._red("MLB Career Leaders for: ") + self._bold(optcategory) + " (+ indicates HOF; " + self._ul("UNDERLINE") + " indicates active.)"
        irc.reply(output)  # header.
        irc.reply(" | ".join([item for item in object_list]))  # now our top10.

    mlbcareerleaders = wrap(mlbcareerleaders, [('somethingWithoutSpaces'), optional('somethingWithoutSpaces')])

    def mlbawards(self, irc, msg, args, optyear):
        """<year>
        Display various MLB award winners for current (or previous) year. Use YYYY for year.
        Ex: 2011
        """

        if optyear:   # crude way to find the latest awards.
            testdate = self._validate(optyear, '%Y')
            if not testdate:
                irc.reply("Invalid year. Must be YYYY.")
                return
        else:
            url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2F3YXJkcy8=')
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return
            soup = BeautifulSoup(html)
            # parse page. find summary. find the first link text. this is our year.
            link = soup.find('big', text="Baseball Award Voting Summaries").findNext('a')['href'].strip()
            optyear = ''.join(i for i in link if i.isdigit())
        # fetch actual page.
        url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2F3YXJkcy8=') + 'awards_%s.shtml' % optyear
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # check if we have the page like if we're not done the 2013 season and someone asks for 2013.
        if "404 - File Not Found" in html:
            irc.reply("ERROR: I found no award summary for {0}".format(optyear))
            return

        # soup since we're past this.
        soup = BeautifulSoup(html)
        alvp = soup.find('h2', text="AL MVP Voting").findNext('table', attrs={'id':'AL_MVP_voting'}).findNext('a').text
        nlvp = soup.find('h2', text="NL MVP Voting").findNext('table', attrs={'id':'NL_MVP_voting'}).findNext('a').text
        alcy = soup.find('h2', text="AL Cy Young Voting").findNext('table', attrs={'id':'AL_Cy_Young_voting'}).findNext('a').text
        nlcy = soup.find('h2', text="NL Cy Young Voting").findNext('table', attrs={'id':'NL_Cy_Young_voting'}).findNext('a').text
        alroy = soup.find('h2', text="AL Rookie of the Year Voting").findNext('table', attrs={'id':'AL_Rookie_of_the_Year_voting'}).findNext('a').text
        nlroy = soup.find('h2', text="NL Rookie of the Year Voting").findNext('table', attrs={'id':'NL_Rookie_of_the_Year_voting'}).findNext('a').text
        almgr = soup.find('h2', text="AL Mgr of the Year Voting").findNext('table', attrs={'id':'AL_Mgr_of_the_Year_voting'}).findNext('a').text
        nlmgr = soup.find('h2', text="NL Mgr of the Year Voting").findNext('table', attrs={'id':'NL_Mgr_of_the_Year_voting'}).findNext('a').text

        output = "{0} MLB Awards :: MVP: AL {1} NL {2}  CY: AL {3} NL {4}  ROY: AL {5} NL {6}  MGR: AL {7} NL {8}".format( \
            self._red(optyear), self._bold(alvp), self._bold(nlvp), self._bold(alcy), self._bold(nlcy),\
            self._bold(alroy), self._bold(nlroy), self._bold(almgr), self._bold(nlmgr))

        irc.reply(output)

    mlbawards = wrap(mlbawards, [optional('somethingWithoutSpaces')])

    def mlbschedule(self, irc, msg, args, optteam):
        """<team>
        Display the last and next five upcoming games for team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return
        # translate team for url.
        lookupteam = self._translateTeam('yahoo', 'team', optteam) # (db, column, optteam)
        # make and fetch url.
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

        # clean this stuff up
        html = html.replace('<![CDATA[','')  #remove cdata
        html = html.replace(']]>','')  # end of cdata
        html = html.replace('EDT','')  # tidy up times
        html = html.replace('\xc2\xa0',' ')  # remove some stupid character.

        soup = BeautifulSoup(html)  # cleans up the RSS because it's broken.
        items = soup.find('channel').findAll('item')

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

        # now output.
        descstring = " | ".join([item for item in append_list])
        output = "{0} :: {1}".format(self._bold(optteam), descstring)
        irc.reply(output)

    mlbschedule = wrap(mlbschedule, [('somethingWithoutSpaces')])

    def mlbmanager(self, irc, msg, args, optteam):
        """<team>
        Display the manager for team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9tYW5hZ2Vycw==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class':re.compile('oddrow|evenrow')})

        managers = collections.defaultdict()

        for row in rows:
            manager = row.find('td').find('a')
            exp = manager.findNext('td')
            record = exp.findNext('td')
            team = record.findNext('td').find('a').getText().strip()
            team = self._translateTeam('team', 'fulltrans', team)
            astring = "{0} :: Manager is {1}({2}) with {3} years experience.".format(\
                self._red(team), self._bold(manager.getText()), record.getText(), exp.getText())
            managers[str(team)] = astring

        # output time.
        output = managers.get(str(optteam), None)
        if not output:
            irc.reply("ERROR: Something went horribly wrong looking up the manager for: {0}".format(optteam))
        else:
            irc.reply(output)

    mlbmanager = wrap(mlbmanager, [('somethingWithoutSpaces')])

    def mlbstandings(self, irc, msg, args, optlist, optdiv):
        """[--expanded|--vsdivision] <ALE|ALC|ALW|NLE|NLC|NLW>
        Display divisional standings for a division.
        Use --expanded or --vsdivision to show extended stats.
        Ex: --expanded ALC
        """

        expanded, vsdivision = False, False
        for (option, arg) in optlist:
            if option == 'expanded':
                expanded = True
            if option == 'vsdivision':
                vsdivision = True

        optdiv = optdiv.lower() # lower to match keys. values are in the table to match with the html.

        leaguetable =   {
                            'ale': 'American League EAST',
                            'alc': 'American League CENTRAL',
                            'alw': 'American League WEST',
                            'nle': 'National League EAST',
                            'nlc': 'National League CENTRAL',
                            'nlw': 'National League WEST'
                        }

        if optdiv not in leaguetable:
            irc.reply("ERROR: League must be one of: %s" % leaguetable.keys())
            return

        # diff urls depending on option.
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

        soup = BeautifulSoup(html) # one of these below will break if formatting changes.
        div = soup.find('div', attrs={'class':'mod-container mod-table mod-no-header'}) # div has all
        table = div.find('table', attrs={'class':'tablehead'}) # table in there
        rows = table.findAll('tr', attrs={'class':re.compile('^oddrow.*?|^evenrow.*?')}) # rows are each team

        object_list = [] # list for ordereddict with each entry.
        lengthlist = collections.defaultdict(list) # sep data structure to determine length.

        for row in rows: # this way, we don't need 100 lines to match with each column. works with multi length.
            league = row.findPrevious('tr', attrs={'class':'stathead'})
            header = row.findPrevious('tr', attrs={'class':'colhead'}).findAll('td')
            tds = row.findAll('td')

            d = collections.OrderedDict()
            division = str(league.getText() + " " + header[0].getText())

            if division == leaguetable[optdiv]: # from table above. only match what we need.
                for i,td in enumerate(tds):
                    if i == 0: # manual replace of team here because the column doesn't say team.
                        d['TEAM'] = str(tds[0].getText())
                        lengthlist['TEAM'].append(len(str(tds[0].getText())))
                    else:
                        d[str(header[i].getText())] = str(td.getText()).replace('  ',' ') # add to ordereddict + conv multispace to one.
                        lengthlist[str(header[i].getText())].append(len(str(td.getText()))) # add key based on header, length of string.
                object_list.append(d)

        if len(object_list) > 0: # now that object_list should have entries, sanity check.
            object_list.insert(0,object_list[0]) # cheap way to copy first item again because we iterate over it for header.
        else: # bailout if something broke.
            irc.reply("ERROR: Something broke returning mlbstandings.")
            return

        for i,each in enumerate(object_list):
            if i == 0: # to print the duplicate but only output the header of the table.
                headerOut = ""
                for keys in each.keys(): # only keys on the first list entry, a dummy/clone.
                    headerOut += "{0:{1}}".format(self._ul(keys),max(lengthlist[keys])+4, key=int) # normal +2 but bold eats up +2 more, so +4.
                irc.reply(headerOut)
            else: # print the division now.
                tableRow = ""
                for inum,k in enumerate(each.keys()):
                    if inum == 0: # team here, which we want to bold.
                        tableRow += "{0:{1}}".format(self._bold(each[k]),max(lengthlist[k])+4, key=int) #+4 since bold eats +2.
                    else: # rest of the elements outside the team.
                        tableRow += "{0:{1}}".format(each[k],max(lengthlist[k])+2, key=int)
                irc.reply(tableRow)

    mlbstandings = wrap(mlbstandings, [getopts({'expanded':'', 'vsdivision':''}), ('somethingWithoutSpaces')])

    def mlblineup(self, irc, msg, args, optteam):
        """<team>
        Gets lineup for MLB team.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL2xpbmV1cHM/d2piPQ==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # have to do some replacing for the regex to work
        html = html.replace('<b  >', '<b>').replace('<b>TAM</b>','<b>TB</b>').replace('<b>WAS</b>','<b>WSH</b>').replace('<b>CHW</b>','<b>CWS</b>')
        html = html.replace('<b>KAN</b>','<b>KC</b>').replace('<b>SDG</b>','<b>SD</b>').replace('<b>SFO</b>','<b>SF</b>')

        outdict = {}

        for matches in re.findall(r'<b>(\w\w+)</b>(.*?)</div>', html, re.I|re.S|re.M):
            team = matches[0].strip()
            lineup = matches[1].strip()
            out = {team:lineup}
            outdict.update(out)

        # output time.
        lineup = outdict.get(optteam)
        if lineup:
            irc.reply("{0:5} - {1}".format(self._bold(optteam), lineup))
        else:
            irc.reply("Could not find lineup for: {0}. Check closer to game time.".format(optteam))
            return

    mlblineup = wrap(mlblineup, [('somethingWithoutSpaces')])

    def mlbinjury(self, irc, msg, args, optlist, optteam):
        """[--details] <team>
        Show all injuries for team.
        Use --details to display full table with team injuries.
        Ex: --details BOS
        """

        details = False
        for (option, arg) in optlist:
            if option == 'details':
                details = True

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        lookupteam = self._translateTeam('roto', 'team', optteam)

        url = self._b64decode('aHR0cDovL3JvdG93b3JsZC5jb20vdGVhbXMvaW5qdXJpZXMvbWxi') + '/%s/' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        # check if we have any injuries.
        if not soup.find('div', attrs={'class': 'player'}):
            #team = soup.find('div', attrs={'class': 'player'}).find('a').text
            irc.reply("No injuries found for: %s" % optteam)
            return
        # if we do, find the table.
        table = soup.find('table', attrs={'align': 'center', 'width': '600px;'})
        t1 = table.findAll('tr')
        object_list = []
        # first is header, rest is injury.
        for row in t1[1:]:
            td = row.findAll('td')
            d = collections.OrderedDict()
            d['name'] = td[0].find('a').getText()
            d['status'] = td[3].getText()
            d['date'] = td[4].getText().strip().replace("&nbsp;", " ")
            d['injury'] = td[5].getText()
            d['returns'] = td[6].getText()
            object_list.append(d)
        # are there any injuries?
        if len(object_list) < 1:
            irc.reply("{0} :: No injuries.".format(self._red(optteam)))
            return
        # output time.
        # conditional if we're showing details or not.
        if details:
            irc.reply("{0} :: {1} Injuries".format(self._red(optteam), len(object_list)))
            irc.reply("{0:25} {1:9} {2:<7} {3:<15} {4:<10}".format("NAME","STATUS","DATE","INJURY","RETURNS"))
            for inj in object_list:  # one per line since we are detailed.
                output = "{0:27} {1:<9} {2:<7} {3:<15} {4:<10}".format(self._bold(\
                    inj['name']), inj['status'], inj['date'], inj['injury'], inj['returns'])
                irc.reply(output)
        else:  # no detail.
            irc.reply("{0} :: {1} Injuries".format(self._red(optteam), len(object_list)))
            irc.reply(" | ".join([item['name'] + " (" + item['returns'] + ")" for item in object_list]))

    mlbinjury = wrap(mlbinjury, [getopts({'details':''}), ('somethingWithoutSpaces')])

    def mlbpowerrankings(self, irc, msg, args):
        """
        Display this week's MLB Power Rankings.
        """

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9wb3dlcnJhbmtpbmdz')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        # process HTML
        soup = BeautifulSoup(html)
        if not soup.find('table', attrs={'class':'tablehead'}):
            irc.reply("Something broke heavily formatting on powerrankings page.")
            return

        # go about regular html business.
        # datehead = soup.find('div', attrs={'class':'date floatleft'})
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
        irc.reply("{0}".format(self._blue(headline.getText())))
        for N in self._batch(powerrankings, 12): # iterate through each team. 12 per line
            irc.reply("{0}".format(" | ".join([item for item in N])))

    mlbpowerrankings = wrap(mlbpowerrankings)

    def mlbteamleaders(self, irc, msg, args, optteam, optcategory):
        """<team> <category>
        Display leaders on a team in stats for a specific category.
        Ex. NYY hr
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        optcategory = optcategory.lower()
        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'r':'runs', 'ab':'atBats', 'obp':'onBasePct',
                    'slug':'slugAvg', 'ops':'OPS', 'sb':'stolenBases', 'runscreated':'runsCreated',
                    'w': 'wins', 'l': 'losses', 'win%': 'winPct', 'era': 'ERA',  'k': 'strikeouts',
                    'k/9ip': 'strikeoutsPerNineInnings', 'holds': 'holds', 's': 'saves',
                    'gp': 'gamesPlayed', 'cg': 'completeGames', 'qs': 'qualityStarts', 'whip': 'WHIP' }

        if optcategory not in category:
            irc.reply("ERROR: Category must be one of: {0}".format(category.keys()))
            return

        lookupteam = self._translateTeam('eid', 'team', optteam)

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RlYW1zdGF0cw==') + '?teamId=%s&lang=EN&category=%s&y=1&wjb=' % (lookupteam, category[optcategory])
        # &season=2012
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'table'})
        rows = table.findAll('tr')

        object_list = []
        # grab the first five and go.
        for row in rows[1:6]:
            tds = row.findAll('td')
            rank = tds[0].getText()
            player = tds[1].getText()
            stat = tds[2].getText()
            object_list.append("{0}. {1} {2}".format(rank, player, stat))

        thelist = " | ".join([item for item in object_list])
        irc.reply("{0} leaders for {1} :: {2}".format(self._red(optteam), self._bold(optcategory.upper()), thelist))

    mlbteamleaders = wrap(mlbteamleaders, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    def mlbleagueleaders(self, irc, msg, args, optleague, optcategory):
        """<MLB|AL|NL> <category>
        Display top 10 teams in category for a specific stat. Categories: hr, avg, rbi, ra, sb, era, whip, k
        Ex: MLB hr or AL rbi or NL era
        """

        league = {'mlb': '9', 'al':'7', 'nl':'8'}  # do our own translation here for league/category.
        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'ra':'runs', 'sb':'stolenBases', 'era':'ERA', 'whip':'whip', 'k':'strikeoutsPerNineInnings'}

        optleague, optcategory = optleague.lower(), optcategory.lower()

        if optleague not in league:
            irc.reply("ERROR: League must be one of: {0}".format(league.keys()))
            return

        if optcategory not in category:
            irc.reply("ERROR: Category must be one of: {0}".format(category.keys()))
            return

        # construct url
        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL2FnZ3JlZ2F0ZXM=')
        url += '?category=%s&groupId=%s&y=1&wjb=' % (category[optcategory], league[optleague])
        # fetch url.
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'table'})
        rows = table.findAll('tr')

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
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        lookupteam = self._translateTeam('eid', 'team', optteam)
        # fetch url.
        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RlYW10cmFuc2FjdGlvbnM=') + '?teamId=%s&wjb=' % lookupteam
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return
        # process html.
        soup = BeautifulSoup(html)
        t1 = soup.findAll('div', attrs={'class':re.compile('ind|ind tL|ind alt')})
        # sanity check.
        if len(t1) < 1:
            irc.reply("ERROR: No transactions found for: {0}".format(optteam))
            return
        else:
            for item in t1:
                if "href=" not in str(item):
                    trans = item.findAll(text=True)
                    irc.reply("{0:8} {1}".format(self._bold(trans[0]), trans[1]))

    mlbteamtrans = wrap(mlbteamtrans, [('somethingWithoutSpaces')])

    def mlbtrans(self, irc, msg, args, optdate):
        """[YYYYmmDD]
        Display all mlb transactions. Will only display today's.
        Use date in format: 20120912 to display other dates.
        """

        if optdate:
            try:
                datetime.datetime.strptime(optdate, '%Y%m%d')
            except:
                irc.reply("ERROR: Date format must be in YYYYMMDD. Ex: 20120714")
                return
        else:
            now = datetime.datetime.now()
            optdate = now.strftime("%Y%m%d")

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RyYW5zYWN0aW9ucz93amI9') + '&date=%s' % optdate
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        if "No transactions today." in html:
            irc.reply("ERROR: No transactions for: {0}".format(optdate))
            return

        soup = BeautifulSoup(html)
        t1 = soup.findAll('div', attrs={'class':re.compile('ind alt|ind')})

        if len(t1) < 1:
            irc.reply("ERROR: I did not find any MLB transactions for: {0}".format(optdate))
            return
        else:
            irc.reply("Displaying all MLB transactions for: {0}".format(self._ul(optdate)))
            for trans in t1:
                if "<a href=" not in trans: # no links
                    match1 = re.search(r'<b>(.*?)</b><br />(.*?)</div>', str(trans), re.I|re.S) #strip out team and transaction
                    if match1:
                        team = match1.group(1) # shorten here?
                        transaction = match1.group(2)
                        irc.reply("{0} - {1}".format(self._red(team), transaction))

    mlbtrans = wrap(mlbtrans, [optional('somethingWithoutSpaces')])

    def mlbprob(self, irc, msg, args, optteam):
        """<TEAM>
        Display the MLB probables for a team over the next 5 stars.
        Ex: NYY
        """

        # test for valid teams.
        optteam = self._validteams(optteam)
        if optteam is 1:  # team is not found in aliases or validteams.
            irc.reply("ERROR: Team not found. Valid teams are: {0}".format(self._allteams()))
            return

        # put the next five dates in a list.
        dates = []
        date = datetime.date.today()
        dates.append(date)
        # add the next four days.
        for i in range(4):
            date += datetime.timedelta(days=1)
            dates.append(date)

        out_array = []

        for eachdate in dates:
            outdate = eachdate.strftime("%Y%m%d")  # date in YYYYmmDD

            url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3Byb2JhYmxlcz93amI9') + '&date=%s' % outdate
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return

            html = html.replace("ind alt tL spaced", "ind tL spaced")

            if "No Games Scheduled" in html:
                next

            html = html.replace('WAS','WSH').replace('CHW','CWS').replace('KAN','KC').replace('TAM','TB').replace('SFO','SF').replace('SDG','SD')

            soup = BeautifulSoup(html)
            t1 = soup.findAll('div', attrs={'class': 'ind tL spaced'})

            for row in t1:
                matchup = row.find('a', attrs={'class': 'bold inline'}).text.strip()
                textmatch = re.search(r'<a class="bold inline".*?<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)$', row.renderContents(), re.I|re.S|re.M)

                if textmatch:
                    d = collections.OrderedDict()
                    d['date'] = outdate
                    d['matchup'] = matchup
                    d['vteam'] = textmatch.group(1).strip().replace(':','')
                    d['vpitcher'] = textmatch.group(2).strip()
                    d['vpstats'] = textmatch.group(3).strip()
                    d['hteam'] = textmatch.group(4).strip().replace(':','')
                    d['hpitcher'] = textmatch.group(5).strip()
                    d['hpstats'] = textmatch.group(6).strip()
                    out_array.append(d)

        for eachentry in out_array:
            if optteam:
                if optteam in eachentry['matchup']:
                    irc.reply("{0:10} {1:25} {2:4} {3:15} {4:15} {5:4} {6:15} {7:15}".format(eachentry['date'], eachentry['matchup'], eachentry['vteam'], \
                        eachentry['vpitcher'],eachentry['vpstats'], eachentry['hteam'], eachentry['hpitcher'], eachentry['hpstats']))

    mlbprob = wrap(mlbprob, [('somethingWithoutSpaces')])

Class = MLB


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=250:
