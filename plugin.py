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
import time
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

    def _validteams(self):
        """Returns a list of valid teams for input verification."""

        with sqlite3.connect(self._mlbdb) as conn:
            cursor = conn.cursor()
            query = "select team from mlb"
            cursor.execute(query)
            teamlist = []
            for row in cursor.fetchall():
                teamlist.append(str(row[0]))

        return teamlist

    def _translateTeam(self, db, column, optteam):
        """Translates optteam into proper string using database"""

        with sqlite3.connect(self._mlbdb) as conn:
            cursor = conn.cursor()
            query = "select %s from mlb where %s='%s'" % (db, column, optteam)
            #self.log.info(query)
            cursor.execute(query)
            row = cursor.fetchone()

            return (str(row[0]))

    ####################
    # PUBLIC FUNCTIONS #
    ####################

    def mlbcountdown(self, irc, msg, args):
        """Display countdown until next MLB opening day."""

        oDay = (datetime.datetime(2014, 03, 31) - datetime.datetime.now()).days
        irc.reply("{0} day(s) until 2014 MLB Opening Day.".format(oDay))

    mlbcountdown = wrap(mlbcountdown)

    def mlbpitcher(self, irc, msg, args, optteam):
        """<TEAM>
        Displays current pitcher(s) in game for a specific team.
        """

        # note: mlbpitcher is normally handled by another bot. only doing
        # this as a supplement until the original bot owner fixes it.
        optteam = optteam.upper()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

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
                teamname = self._translateTeam('team', 'eshort', teamname)  # fix the espn discrepancy.
                teamdict[str(teamname)] = team['id'].replace('-aNameOffset', '').replace('-hNameOffset', '')
        # grab the gameid. fetch.
        teamgameid = teamdict.get(optteam)
        # self.log.info(str(teamdict))
        # sanity check before we grab the game.
        if not teamgameid:
            self.log.info("ERROR: I got {0} as a team. I only have: {1}".format(optteam, str(teamdict)))
            irc.reply("ERROR: No upcoming/active games with: {0}".format(optteam))
            return
        # we have gameid. refetch boxscore for page.
        # now we fetch the game box score to find the pitchers.
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
        Display results for a MLB World Series that year. Ex: 2000. Earliest year is 1903 and latest is the last postseason.
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
            output = "{0} :: {1}".format(self._red('red'), descstring)
            irc.reply(output)

    mlbcyyoung = wrap(mlbcyyoung)


    def mlbheadtohead(self, irc, msg, args, optteam, optopp):
        """<team> <opp>
        Display the record between two teams head-to-head. EX: NYY BOS
        Ex: NYY BOS
        """

        optteam, optopp = optteam.upper(), optopp.upper()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        if optopp not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        if optteam == optopp:
            irc.reply("error: Must have different teams in mlbheadtohead")
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3MvZ3JpZA==')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

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

        optteam, optopp = optteam.upper(), optopp.upper()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        if optopp not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        currentYear = str(datetime.date.today().year) # need as a str.

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
                append_list.append(mDate + " - " + ircutils.bold(mOpp) + " " + mTime)

        for each in append_list: # here, we go through all remaining games, only pick the ones with the opp in it, and go from there.
            if optopp in each: # this is real cheap using string matching instead of assigning keys, but easier.
                out_list.append(each)

        if len(out_list) > 0:
            descstring = string.join([item for item in out_list], " | ")
            output = "There are {0} games between {1} and {2} :: {3}".format(self._red(len(out_list)), self._bold(optteam), self._bold(optopp), descstring)
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
        ejectedTotal = soup.find('div', attrs={'class':'sites-list-showing-items'}).find('span')
        table = soup.find('table', attrs={'id':'goog-ws-list-table', 'class':'sites-table goog-ws-list-table'})
        rows = table.findAll('tr')[1:6]  # last 5. header row is 0.

        append_list = []

        for row in rows:
            date = row.find('td')
            number = date.findNext('td')
            pnum = number.findNext('td')
            mnum = pnum.findNext('td')
            unum = mnum.findNext('td')
            umppos = unum.findNext('td')
            umpname = umppos.findNext('td')
            ejteam = umpname.findNext('td')
            ejpos = ejteam.findNext('td')
            ejected = ejpos.findNext('td')
            date = date.getText()
            date = self._dtFormat('%m/%d', date, '%B %d, %Y') # March 27, 2013

            append_list.append("{0} - {1} ejected {2} ({3})".format(date, umpname.getText(), ejected.getText(), ejpos.getText()))

        descstring = " | ".join([item for item in append_list])
        irc.reply("There have been {0} ejections this season. Last five :: {1}".format(self._red(ejectedTotal.getText()), descstring))

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

        (first, last) = optplayer.split(" ", 1)  #playername needs to be "first-last"
        searchplayer = first + '-' + last

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

        soup = BeautifulSoup(html)

        if not soup.find('li', attrs={'class':'result mod-smart-card'}):
            irc.reply("I didn't find a link for: %s. Perhaps you should be more specific and give a full playername" % optplayer)
            return
        else:
            playercard = soup.find('li', attrs={'class':'result mod-smart-card'})

        if 'http://espn.go.com/mlb/players/stats?playerId=' not in playercard.renderContents():
            irc.reply("Could not find a link to career stats for: %s" % optplayer)
            return
        else:
            link = playercard.find('a', attrs={'href':re.compile('.*?espn.go.com/mlb/players/stats.*?')})['href']

        if not link:
            irc.reply("I didn't find the link I needed for career stats. Did something break?")
            return
        else:
            html = self._httpget(url)
            if not html:
                irc.reply("ERROR: Failed to fetch {0}.".format(url))
                self.log.error("ERROR opening {0}".format(url))
                return

        soup = BeautifulSoup(html)
        # playerName = soup.find('title')
        table = soup.find('table', attrs={'class':'tablehead'}) # everything stems from the table.
        header = table.find('tr', attrs={'class':'colhead'}).findAll('td') # columns to reference.

        if optyear:
            seasonrows = table.findAll('tr', attrs={'class':re.compile('^oddrow$|^evenrow$')}) # find all outside the season+totals
            season_data = collections.defaultdict(list) # key will be the year.

            for row in seasonrows:
                tds = row.findAll('td')
                for i,td in enumerate(tds):
                    season_data[str(tds[0].getText())].append(str(ircutils.bold(header[i].getText()) + ": " + td.getText()))

            outyear = season_data.get(str(optyear), None)

            if not outyear:
                irc.reply("No stats found for %s in %s" % (optplayer, optyear))
            else:
                outyear = " | ".join([item for item in outyear])
                irc.reply("{0} :: {1}".format(optplayer, outyear))
        else:
            endrows = table.findAll('tr', attrs={'class':re.compile('^evenrow bi$|^oddrow bi$')})

            for total in endrows:
                if total.find('td', text="Total"):
                    totals = total.findAll('td')
                if total.find('td', text="Season Averages"):
                    seasonaverages = total.findAll('td')

            del seasonaverages[0] #remove the first td, but match up header via j+2
            del totals[0:2]

            seasonstring = " | ".join([header[i+2].getText() + ": " + td.getText() for i,td in enumerate(seasonaverages)])
            totalstring = " | ".join([header[i+2].getText() + ": " + td.getText() for i,td in enumerate(totals)])

            irc.reply("{0} Season Averages :: {1}".format(self._bold(optplayer), seasonstring))
            irc.reply("{0} Career Totals :: {1}".format(self._bold(optplayer), totalstring))

    mlbstats = wrap(mlbstats, [(getopts({'year':('int')})), ('text')])

    def mlbgamesbypos (self, irc, msg, args, optteam):
        """<team>
        Display a team's games by position. Ex: NYY
        """

        optteam = optteam.upper()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        if optteam == 'CWS':  # didn't want a new table here for one site, so this is a cheap stop-gap.
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
        output = "{0} :: {1}".format(self._red(optteam.upper()), descstring)

        irc.reply(output)

    mlbgamesbypos = wrap(mlbgamesbypos, [('somethingWithoutSpaces')])

    def mlbroster(self, irc, msg, args, optlist, optteam):
        """[--40man|--active] <team>
        Display active roster for team.
        Defaults to active roster but use --40man switch to show the entire roster.
        Ex: --40man NYY
        """

        optteam = optteam.upper()

        if optteam not in self._validteams():
            irc.reply("ERROR: Team not found. Must be one of: %s" % self._validteams())
            return

        active, fortyman = True, False
        for (option, arg) in optlist:
            if option == 'active':
                active, fortyman = True, False
            if option == '40man':
                active, fortyman = False, True

        if optteam == 'CWS': # didn't want a new table here for one site, so this is a cheap stop-gap.
            optteam = 'chw'
        else:
            optteam = optteam.lower()

        if active and not fortyman:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL3Jvc3Rlci9fL25hbWU=') + '/%s/type/active/' % optteam
        else: # 40man
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

        for i, j in team_data.iteritems():
            output = "{0} {1} :: {2}".format(self._red(optteam.upper()), self._bold(i), " | ".join([item for item in j]))
            irc.reply(output)

    mlbroster = wrap(mlbroster, [getopts({'active':'','40man':''}), ('somethingWithoutSpaces')])


    def mlbrosterstats(self, irc, msg, args, optteam):
        """[team]
        Displays top 5 youngest/oldest teams.
        Optionally, use TEAM as argument to display roster stats/averages for MLB team. Ex: NYY
        """

        if optteam:
            optteam = optteam.upper()
            if optteam not in self._validteams():
                irc.reply("Team not found. Must be one of: %s" % self._validteams())
                return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy9yb3N0ZXJz')
        html = self._httpget(url)
        if not html:
            irc.reply("ERROR: Failed to fetch {0}.".format(url))
            self.log.error("ERROR opening {0}".format(url))
            return

        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr')[2:]

        object_list = []

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

        if optteam:
            for each in object_list:
                if each['team'] == optteam:  # list will have all teams so we don't need to check
                    output = "{0} Roster Stats :: {1}".format(self._red(each['team']), each['data'])
            irc.reply(output)
        else:
            output = "{0} :: {1}".format(self._bold("5 Youngest MLB Teams:"), " | ".join([item['team'] for item in object_list[0:5]]))
            irc.reply(output)

            output = "{0} :: {1}".format(self._bold("5 Oldest MLB Teams:"), " | ".join([item['team'] for item in object_list[-6:-1]]))
            irc.reply(output)

    mlbrosterstats = wrap(mlbrosterstats, [optional('somethingWithoutSpaces')])

    def mlbteamsalary(self, irc, msg, args, optteam):
        """<team>
        Display top 5 salaries for <team>. Ex: Yankees
        """

        optteam = optteam.upper()
        if optteam not in self._validteams():
            irc.reply("ERROR: Team not found. Must be one of: %s" % self._validteams())
            return

    mlbteamsalary = wrap(mlbteamsalary, [('text')])

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

        #html = html.replace('&nbsp;',' ')
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

        teams = self._validteams()
        irc.reply("Valid MLB teams are: %s" % (" | ".join([item for item in teams])))

    mlbteams = wrap(mlbteams)

    def mlbweather(self, irc, msg, args, optteam):
        """<team>
        Display weather for MLB team at park they are playing at.
        """

        optteam = optteam.upper()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
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
                #NYY at DET, 1:05PM ET at Comerica Park(+101)  Weather: mostly cloudy, 53F Gentle breeze out to left-center. Later: mostly cloudy  Wind: 12mph (345deg)
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
        """Display current MLB team valuations from Forbes."""

        url = self._b64decode('aHR0cDovL3d3dy5mb3JiZXMuY29tL21sYi12YWx1YXRpb25zL2xpc3Qv')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to load: %s" % url)
            return

        soup = BeautifulSoup(html)
        tbody = soup.find('tbody', attrs={'id':'listbody'})
        rows = tbody.findAll('tr')

        object_list = []

        for row in rows:
            rank = row.find('td', attrs={'class':'rank'})
            team = rank.findNext('td')
            value = team.findNext('td')
            yrchange = value.findNext('td')
            debtvalue = yrchange.findNext('td')
            revenue = debtvalue.findNext('td')
            operinc = revenue.findNext('td')
            d = collections.OrderedDict()
            d['rank'] = rank.renderContents().strip()
            d['team'] = team.find('h3').renderContents().strip()
            d['value'] = value.renderContents().strip()
            d['yrchange'] = yrchange.renderContents().strip()
            d['debtvalue'] = debtvalue.renderContents().strip()
            d['revenue'] = revenue.renderContents().strip()
            d['operinc'] = operinc.renderContents().strip()
            object_list.append(d)

        irc.reply(ircutils.mircColor("Current MLB Team Values", 'red') + " (in millions):")

        for N in self._batch(object_list, 7):
            irc.reply(' '.join(str(str(n['rank']) + "." + " " + ircutils.bold(n['team'])) + " (" + n['value'] + "M)" for n in N))

    mlbvaluations = wrap(mlbvaluations)


    def mlbremaining(self, irc, msg, args, optteam):
        """[team]
        Display remaining games/schedule for a playoff contender.
        """

        optteam = optteam.upper()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9odW50Zm9yb2N0b2Jlcg==')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
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
        """Display playoff matchups if season ended today."""

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9odW50Zm9yb2N0b2Jlcg==')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply('Failed to fetch: %s' % (self._b64decode('url')))
            return

        html = html.replace('sdg', 'sd').replace('sfo', 'sf').replace('tam', 'tb').replace('was', 'wsh').replace('kan', 'kc').replace('chw', 'cws')

        soup = BeautifulSoup(html)
        each = soup.findAll('td', attrs={'width':'25%'})

        ol = []

        for ea in each: # man is this just a horrible stopgap.
            links = ea.findAll('a')
            for link in links:
                linksplit = link['href'].split('/')
                team = linksplit[7]
                ol.append(team.upper())

        irc.reply("Playoffs: AL ({0} vs {1}) vs. {2} | {3} vs. {4} || NL: ({5} vs. {6}) vs. {7} | {8} vs. {9}".format(\
            ircutils.bold(ol[0]), ircutils.bold(ol[1]), ircutils.bold(ol[2]), ircutils.bold(ol[3]), ircutils.bold(ol[4]),\
            ircutils.bold(ol[5]), ircutils.bold(ol[6]), ircutils.bold(ol[7]), ircutils.bold(ol[8]), ircutils.bold(ol[9])))

    mlbplayoffs = wrap(mlbplayoffs)

    def mlbcareerleaders(self, irc, msg, args, optplayertype, optcategory):
        """[batting|pitching] [category]
        Must specify batting or pitching.
        Display career leaders in a specific stat.
        """

        optplayertype = optplayertype.lower()

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

        url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2xlYWRlcnMv') + endurl

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failure to fetch: %s" % url)
            return

        html = html.replace('&nbsp;',' ')

        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'data-crop':'50'})
        rows = table.findAll('tr')

        object_list = []

        for row in rows[1:11]:

            rank = row.find('td', attrs={'align':'right'})
            player = rank.findNext('td')
            stat = player.findNext('td')
            if player.find('strong'):
                player = ircutils.underline(player.find('a').find('strong').renderContents().strip())
            else:
                player = player.find('a').renderContents()
            d = collections.OrderedDict()
            d['rank'] = rank.renderContents().strip()
            d['player'] = player
            d['stat'] = stat.renderContents().strip()
            object_list.append(d)

        output = "MLB Career Leaders for: " + optcategory + " (+ indicates HOF; "
        output += ircutils.underline("UNDERLINE") + " indicates active.)"
        irc.reply(output)

        for N in self._batch(object_list, 5):
            irc.reply(' '.join(str(str(n['rank']) + " " + ircutils.bold(n['player'])) + " (" + n['stat'] + ") " for n in N))

    mlbcareerleaders = wrap(mlbcareerleaders, [('somethingWithoutSpaces'), optional('somethingWithoutSpaces')])


    def mlbawards(self, irc, msg, args, optyear):
        """<year>
        Display various MLB awards for current (or previous) year. Use YYYY for year. Ex: 2011
        """

        if optyear: # crude way to find the latest awards.
            testdate = self._validate(optyear, '%Y')
            if not testdate:
                irc.reply("Invalid year. Must be YYYY.")
                return
        else:
            url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2F3YXJkcy8=')
            req = urllib2.Request(url)
            response = urllib2.urlopen(req)
            html = response.read()
            soup = BeautifulSoup(html) #
            link = soup.find('big', text="Baseball Award Voting Summaries").findNext('a')['href'].strip()
            optyear = ''.join(i for i in link if i.isdigit())

        url = self._b64decode('aHR0cDovL3d3dy5iYXNlYmFsbC1yZWZlcmVuY2UuY29tL2F3YXJkcy8=') + 'awards_%s.shtml' % optyear

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failure to load: %s" % url)
            return

        # soup
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
            ircutils.mircColor(optyear, 'red'), ircutils.bold(alvp),ircutils.bold(nlvp), \
            ircutils.bold(alcy),ircutils.bold(nlcy),ircutils.bold(alroy),ircutils.bold(nlroy), ircutils.bold(almgr),ircutils.bold(nlmgr))

        irc.reply(output)

    mlbawards = wrap(mlbawards, [optional('somethingWithoutSpaces')])


    def mlbschedule(self, irc, msg, args, optteam):
        """[team]
        Display the last and next five upcoming games for team.
        """

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        lookupteam = self._translateTeam('yahoo', 'team', optteam) # (db, column, optteam)

        url = self._b64decode('aHR0cDovL3Nwb3J0cy55YWhvby5jb20vbWxiL3RlYW1z') + '/%s/calendar/rss.xml' % lookupteam

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Cannot open: %s" % url)
            return

        if "Schedule for" not in html:
            irc.reply("Cannot find schedule. Broken url?")
            return

        # clean this stuff up
        html = html.replace('<![CDATA[','') #remove cdata
        html = html.replace(']]>','') # end of cdata
        html = html.replace('EDT','') # tidy up times
        html = html.replace('\xc2\xa0',' ') # remove some stupid character.

        soup = BeautifulSoup(html)
        items = soup.find('channel').findAll('item')

        append_list = []

        for item in items:
            title = item.find('title').renderContents().strip() # title is good.
            day, date = title.split(',')
            desc = item.find('description') # everything in desc but its messy.
            desctext = desc.findAll(text=True) # get all text, first, but its in a list.
            descappend = (''.join(desctext).strip()) # list transform into a string.
            if not descappend.startswith('@'): # if something is @, it's before, but vs. otherwise.
                descappend = 'vs. ' + descappend
            descappend += " [" + date.strip() + "]" # can't translate since Yahoo! sucks with the team names here.
            append_list.append(descappend) # put all into a list.

        descstring = string.join([item for item in append_list], " | ")
        output = "{0} {1}".format(ircutils.bold(optteam), descstring)

        irc.reply(output)

    mlbschedule = wrap(mlbschedule, [('somethingWithoutSpaces')])


    def mlbmanager(self, irc, msg, args, optteam):
        """[team]
        Display the manager for team.
        """

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9tYW5hZ2Vycw==')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Cannot fetch URL: %s" % url)
            return

        # change some strings to parse better.
        html = html.replace('class="evenrow', 'class="oddrow')

        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class':'oddrow'})

        object_list = []

        for row in rows:
            manager = row.find('td').find('a')
            exp = manager.findNext('td')
            record = exp.findNext('td')
            team = record.findNext('td').find('a').renderContents().strip()

            d = collections.OrderedDict()
            d['manager'] = manager.renderContents().strip().replace('  ',' ')
            d['exp'] = exp.renderContents().strip()
            d['record'] = record.renderContents().strip()
            d['team'] = self._translateTeam('team', 'fulltrans', team) # translate from full to short
            object_list.append(d)

        for each in object_list:
            if each['team'] == optteam:
                output = "Manager of {0} is {1}({2}) with {3} years experience.".format( \
                    ircutils.bold(each['team']), ircutils.bold(each['manager']), each['record'], each['exp'])
                irc.reply(output)

    mlbmanager = wrap(mlbmanager, [('somethingWithoutSpaces')])


    def mlbstandings(self, irc, msg, args, optlist, optdiv):
        """<--expanded|--vsdivision> [ALE|ALC|ALW|NLE|NLC|NLW]
        Display divisional standings for a division. Use --expanded or --vsdivision
        to show extended stats.
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
            irc.reply("League must be one of: %s" % leaguetable.keys())
            return

        if expanded:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3MvXy90eXBlL2V4cGFuZGVk')
        elif vsdivision:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3MvXy90eXBlL3ZzLWRpdmlzaW9u')
        else:
            url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGFuZGluZ3M=')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Problem opening up: %s" % url)
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
            irc.reply("Something broke returning mlbstandings.")
            return

        for i,each in enumerate(object_list):
            if i == 0: # to print the duplicate but only output the header of the table.
                headerOut = ""
                for keys in each.keys(): # only keys on the first list entry, a dummy/clone.
                    headerOut += "{0:{1}}".format(ircutils.underline(keys),max(lengthlist[keys])+4, key=int) # normal +2 but bold eats up +2 more, so +4.
                irc.reply(headerOut)
            else: # print the division now.
                tableRow = ""
                for inum,k in enumerate(each.keys()):
                    if inum == 0: # team here, which we want to bold.
                        tableRow += "{0:{1}}".format(ircutils.bold(each[k]),max(lengthlist[k])+4, key=int) #+4 since bold eats +2.
                    else: # rest of the elements outside the team.
                        tableRow += "{0:{1}}".format(each[k],max(lengthlist[k])+2, key=int)
                irc.reply(tableRow)


    mlbstandings = wrap(mlbstandings, [getopts({'expanded':'', 'vsdivision':''}), ('somethingWithoutSpaces')])


    def mlblineup(self, irc, msg, args, optteam):
        """<team>
        Gets lineup for MLB team. Example: NYY
        """

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL2xpbmV1cHM/d2piPQ==')

        self.log.info(url)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Problem fetching: %s" % url)
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

        lineup = outdict.get(optteam)
        if lineup != None:
            output = "{0:5} - {1:150}".format(ircutils.bold(optteam), lineup)
            irc.reply(output)
        else:
            irc.reply("Could not find lineup for: %s. Check closer to game time." % optteam)
            return

    mlblineup = wrap(mlblineup, [('somethingWithoutSpaces')])


    def mlbinjury(self, irc, msg, args, optlist, optteam):
        """<--details> [TEAM]
        Show all injuries for team. Example: BOS or NYY. Use --details to
        display full table with team injuries.
        """

        details = False
        for (option, arg) in optlist:
            if option == 'details':
                details = True

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        lookupteam = self._translateTeam('roto', 'team', optteam)

        url = self._b64decode('aHR0cDovL3JvdG93b3JsZC5jb20vdGVhbXMvaW5qdXJpZXMvbWxi') + '/%s/' % lookupteam

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to grab: %s" % url)
            return

        soup = BeautifulSoup(html)
        if soup.find('div', attrs={'class': 'player'}):
            team = soup.find('div', attrs={'class': 'player'}).find('a').text
        else:
            irc.reply("No injuries found for: %s" % optteam)
            return
        table = soup.find('table', attrs={'align': 'center', 'width': '600px;'})
        t1 = table.findAll('tr')

        object_list = []

        for row in t1[1:]:
            td = row.findAll('td')
            d = collections.OrderedDict()
            d['name'] = td[0].find('a').text
            d['position'] = td[2].renderContents().strip()
            d['status'] = td[3].renderContents().strip()
            d['date'] = td[4].renderContents().strip().replace("&nbsp;", " ")
            d['injury'] = td[5].renderContents().strip()
            d['returns'] = td[6].renderContents().strip()
            object_list.append(d)

        if len(object_list) < 1:
            irc.reply("No injuries for: %s" % optteam)

        if details:
            irc.reply(ircutils.underline(str(team)) + " - " + str(len(object_list)) + " total injuries")
            irc.reply("{0:25} {1:3} {2:6} {3:<7} {4:<15} {5:<10}".format("Name","POS","Status","Date","Injury","Returns"))

            for inj in object_list:
                output = "{0:27} {1:<3} {2:<6} {3:<7} {4:<15} {5:<10}".format(ircutils.bold( \
                    inj['name']),inj['position'],inj['status'],inj['date'],inj['injury'],inj['returns'])
                irc.reply(output)
        else:
            irc.reply(ircutils.underline(str(team)) + " - " + str(len(object_list)) + " total injuries")
            irc.reply(string.join([item['name'] + " (" + item['returns'] + ")" for item in object_list], " | "))

    mlbinjury = wrap(mlbinjury, [getopts({'details':''}), ('somethingWithoutSpaces')])


    def mlbpowerrankings(self, irc, msg, args):
        """
        Display this week's MLB Power Rankings.
        """

        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9wb3dlcnJhbmtpbmdz')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to fetch: %s" % url)
            return

        html = html.replace("evenrow", "oddrow")

        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class': 'tablehead'})
        prdate = table.find('td', attrs={'colspan': '6'}).renderContents()
        t1 = table.findAll('tr', attrs={'class': 'oddrow'})

        if len(t1) < 30:
            irc.reply("Failed to parse MLB Power Rankings. Did something break?")
            return

        object_list = []

        for row in t1:
            rowrank = row.find('td', attrs={'class': 'pr-rank'}).renderContents().strip()
            rowteam = row.find('div', attrs={'style': re.compile('^padding.*')}).find('a').text.strip()
            rowrecord = row.find('span', attrs={'class': 'pr-record'}).renderContents().strip()
            rowlastweek = row.find('span', attrs={'class': 'pr-last'}).renderContents().strip().replace("Last Week", "prev")

            d = collections.OrderedDict()
            d['rank'] = int(rowrank)
            d['team'] = str(rowteam)
            d['record'] = str(rowrecord)
            d['lastweek'] = str(rowlastweek)
            object_list.append(d)

        if prdate:
            irc.reply(ircutils.mircColor(prdate, 'blue'))

        for N in self._batch(object_list, 6):
            irc.reply(' '.join(str(str(n['rank']) + "." + " " + ircutils.bold(n['team'])) + " (" + n['lastweek'] + ")" for n in N))

    mlbpowerrankings = wrap(mlbpowerrankings)


    def mlbteamleaders(self, irc, msg, args, optteam, optcategory):
        """[TEAM] [category]
        Display leaders on a team in stats for a specific category.
        Ex. NYY hr
        """

        optteam = optteam.upper().strip()
        optcategory = optcategory.lower().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'r':'runs', 'ab':'atBats', 'obp':'onBasePct',
                    'slug':'slugAvg', 'ops':'OPS', 'sb':'stolenBases', 'runscreated':'runsCreated',
                    'w': 'wins', 'l': 'losses', 'win%': 'winPct', 'era': 'ERA',  'k': 'strikeouts',
                    'k/9ip': 'strikeoutsPerNineInnings', 'holds': 'holds', 's': 'saves',
                    'gp': 'gamesPlayed', 'cg': 'completeGames', 'qs': 'qualityStarts', 'whip': 'WHIP' }

        if optcategory not in category:
            irc.reply("Error. Category must be one of: %s" % category.keys())
            return

        lookupteam = self._translateTeam('eid', 'team', optteam)

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RlYW1zdGF0cw==') + '?teamId=%s&lang=EN&category=%s&y=1&wjb=' % (lookupteam, category[optcategory])
        # &season=2012

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to fetch: %s" % url)
            return

        html = html.replace('<b  >', '<b>')
        html = html.replace('class="ind alt', 'class="ind')
        html = html.replace('class="ind tL', 'class="ind')

        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'table'})
        rows = table.findAll('tr')

        object_list = []

        for row in rows[1:6]: # grab the first through ten.
            rank = row.find('td', attrs={'class':'ind', 'width': '10%'}).renderContents().strip()
            player = row.find('td', attrs={'class':'ind', 'width': '65%'}).find('a').renderContents().strip()
            stat = row.find('td', attrs={'class':'ind', 'width': '25%'}).renderContents().strip()
            object_list.append(rank + ". " + player + " " + stat)

        thelist = string.join([item for item in object_list], " | ")
        irc.reply("Leaders in %s for %s: %s" % (ircutils.bold(optteam.upper()), ircutils.bold(optcategory.upper()), thelist))

    mlbteamleaders = wrap(mlbteamleaders, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])


    def mlbleagueleaders(self, irc, msg, args, optleague, optcategory):
        """[MLB|AL|NL] [category]
        Display leaders (top 5) in category for teams in the MLB.
        Categories: hr, avg, rbi, ra, sb, era, whip, k
        """

        league = {'mlb': '9', 'al':'7', 'nl':'8'} # do our own translation here for league/category.
        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'ra':'runs', 'sb':'stolenBases', 'era':'ERA', 'whip':'whip', 'k':'strikeoutsPerNineInnings'}

        optleague = optleague.lower()
        optcategory = optcategory.lower()

        if optleague not in league:
            irc.reply("League must be one of: %s" % league.keys())
            return

        if optcategory not in category:
            irc.reply("Category must be one of: %s" % category.keys())
            return

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL2FnZ3JlZ2F0ZXM=') + '?category=%s&groupId=%s&y=1&wjb=' % (category[optcategory], league[optleague])

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to fetch: %s" % url)
            return

        html = html.replace('class="ind alt nw"', 'class="ind nw"')

        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'table'})
        rows = table.findAll('tr')

        append_list = []

        for row in rows[1:6]:
            rank = row.find('td', attrs={'class':'ind nw', 'nowrap':'nowrap', 'width':'10%'}).renderContents()
            team = row.find('td', attrs={'class':'ind nw', 'nowrap':'nowrap', 'width':'70%'}).find('a').text
            num = row.find('td', attrs={'class':'ind nw', 'nowrap':'nowrap', 'width':'20%'}).renderContents()
            append_list.append(rank + ". " + team + " " + num)

        thelist = string.join([item for item in append_list], " | ")

        irc.reply("Leaders in %s for %s: %s" % (ircutils.bold(optleague.upper()), ircutils.bold(optcategory.upper()), thelist))

    mlbleagueleaders = wrap(mlbleagueleaders, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])


    def mlbrumors(self, irc, msg, args):
        """
        Display the latest mlb rumors.
        """

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3J1bW9ycz93amI9')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Something broke trying to read: %s" % url)
            return

        html = html.replace('<div class="ind alt">', '<div class="ind">')

        soup = BeautifulSoup(html)
        t1 = soup.findAll('div', attrs={'class': 'ind'})

        if len(t1) < 1:
            irc.reply("No mlb rumors found. Check formatting?")
            return
        for t1rumor in t1[0:7]:
            item = t1rumor.find('div', attrs={'class': 'noborder bold tL'}).renderContents()
            item = re.sub('<[^<]+?>', '', item)
            rumor = t1rumor.find('div', attrs={'class': 'inline rumorContent'}).renderContents().replace('\r','')
            irc.reply(ircutils.bold(item) + " :: " + rumor)

    mlbrumors = wrap(mlbrumors)


    def mlbteamtrans(self, irc, msg, args, optteam):
        """[team]
        Shows recent MLB transactions for [team]. Ex: NYY
        """

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        lookupteam = self._translateTeam('eid', 'team', optteam)

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RlYW10cmFuc2FjdGlvbnM=') + '?teamId=%s&wjb=' % lookupteam
        self.log.info(url)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to load: %s" % url)
            return

        html = html.replace('<div class="ind tL"','<div class="ind"').replace('<div class="ind alt"','<div class="ind"')

        soup = BeautifulSoup(html)
        t1 = soup.findAll('div', attrs={'class': 'ind'})

        if len(t1) < 1:
            irc.reply("No transactions found for %s" % optteam)
            return

        for item in t1:
            if "href=" not in str(item):
                trans = item.findAll(text=True)
                irc.reply("{0:8} {1}".format(ircutils.bold(str(trans[0])), str(trans[1])))

    mlbteamtrans = wrap(mlbteamtrans, [('somethingWithoutSpaces')])


    def mlbtrans(self, irc, msg, args, optdate):
        """[YYYYmmDD]
        Display all mlb transactions. Will only display today's. Use date in format: 20120912
        """

        url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3RyYW5zYWN0aW9ucz93amI9')

        if optdate:
            try:
                #time.strptime(optdate, '%Y%m%d') # test for valid date
                datetime.datetime.strptime(optdate, '%Y%m%d')
            except:
                irc.reply("ERROR: Date format must be in YYYYMMDD. Ex: 20120714")
                return
        else:
            now = datetime.datetime.now()
            optdate = now.strftime("%Y%m%d")

        url += '&date=%s' % optdate

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Something broke trying to read: %s" % url)
            return

        if "No transactions today." in html:
            irc.reply("No transactions for: %s" % optdate)
            return

        soup = BeautifulSoup(html)
        t1 = soup.findAll('div', attrs={'class': 'ind alt'})
        t1 += soup.findAll('div', attrs={'class': 'ind'})

        out_array = []

        for trans in t1:
            if "<a href=" not in trans: # no links
                match1 = re.search(r'<b>(.*?)</b><br />(.*?)</div>', str(trans), re.I|re.S) #strip out team and transaction
                if match1:
                    team = match1.group(1)
                    transaction = match1.group(2)
                    output = ircutils.mircColor(team, 'red') + " - " + ircutils.bold(transaction)
                    out_array.append(output)

        if len(out_array) > 0:
            for output in out_array:
                irc.reply(output)
        else:
            irc.reply("Did something break?")
            return

    mlbtrans = wrap(mlbtrans, [optional('somethingWithoutSpaces')])


    def mlbprob(self, irc, msg, args, optteam):
        """<TEAM>
        Display the MLB probables for a team over the next 5 stars. Ex: NYY
        """

        # without optdate and optteam, we only do a single day (today)
        # with optdate and optteam, show only one date with one team
        # with no optdate and optteam, show whatever the stuff today is.
        # with optdate and no optteam, show all matches that day.

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        dates = []
        date = datetime.date.today()
        dates.append(date)

        for i in range(4):
            date += datetime.timedelta(days=1)
            dates.append(date)

        out_array = []

        for eachdate in dates:
            outdate = eachdate.strftime("%Y%m%d")
            url = self._b64decode('aHR0cDovL20uZXNwbi5nby5jb20vbWxiL3Byb2JhYmxlcz93amI9') + '&date=%s' % outdate

            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read().replace("ind alt tL spaced", "ind tL spaced")

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
