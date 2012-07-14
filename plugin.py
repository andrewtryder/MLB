##
# Copyright (c) 2012, spline
# All rights reserved.
#
#
###

from BeautifulSoup import BeautifulSoup
import urllib2
import re
import collections
from itertools import izip, chain, repeat
import datetime
import string

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

    # from: http://bytes.com/topic/python/answers/524017-printing-n-elements-per-line-list#post2043945
    def _grouper(self, n, iterable, padvalue=None):
        """
        Return n-tuples from iterable, padding with padvalue.
        Example:
        grouper(3, 'abcdefg', 'x') -->
        ('a','b','c'), ('d','e','f'), ('g','x','x')
        """
        return izip(*[chain(iterable, repeat(padvalue, n-1))]*n)

    # rotoworld uses jacked up team abbrs sometimes.
    def _rototrans(self, tid):
        rototrans = {'BAL':'BAL', 'BOS':'BOS', 'LAA':'ANA', 'CWS':'CWS', 'CLE':'CLE',
                    'DET':'DET', 'KC':'KC', 'MIL':'MLW', 'MIN':'MIN', 'NYY':'NYY',
                    'OAK':'OAK', 'SEA':'SEA', 'TEX':'TEX', 'TOR':'TOR', 'ATL':'ATL',
                    'CHC':'CHC', 'CIN':'CIN', 'HOU':'HOU', 'LAD':'LA', 'WSH':'WAS',
                    'NYM':'NYM', 'PHI':'PHI', 'PIT':'PIT', 'STL':'STL', 'SD':'SD',
                    'SF':'SF', 'COL':'COL', 'MIA':'FLA', 'ARI':'ARZ', 'TB':'TB'}
        return rototrans[tid]

    # espn likes to use tID.
    def _espntrans(self, tid):
        espntrans = {'BAL':'1', 'BOS':'2', 'LAA':'3', 'CWS':'4', 'CLE':'5',
                    'DET':'6', 'KC':'7', 'MIL':'8', 'MIN':'9', 'NYY':'10',
                    'OAK':'11', 'SEA':'12', 'TEX':'13', 'TOR':'14', 'ATL':'15',
                    'CHC':'16', 'CIN':'17', 'HOU':'18', 'LAD':'19', 'WSH':'20', 'WAS':'20',
                    'NYM':'21', 'PHI':'22', 'PIT':'23', 'STL':'24', 'SD':'25',
                    'SF':'26', 'SFG':'26', 'COL':'27', 'MIA':'28', 'ARI':'29', 'TB':'30'}
        return espntrans[tid]

    def _fulltoshort(self, lookupkey):
        fullteams = {   'Arizona Diamondbacks':'ARI', 'Arizona':'ARI',
                        'Atlanta Braves':'ATL', 'Atlanta':'ATL',
                        'Baltimore Orioles':'BAL', 'Baltimore':'BAL',
                        'Boston Red Sox': 'BOS', 'Boston':'BOS',
                        'Chicago Cubs': 'CHC', 'Chicago Cubs':'CHC',
                        'Chicago White Sox': 'CWS', 'Chicago Sox':'CWS',
                        'Cincinnati Reds': 'CIN', 'Cincinnati':'CIN',
                        'Cleveland Indians': 'CLE', 'Cleveland':'CLE',
                        'Colorado Rockies': 'COL', 'Colorado':'COL',
                        'Detroit Tigers': 'DET', 'Detroit':'DET',
                        'Houston Astros': 'HOU', 'Houston':'HOU',
                        'Kansas City Royals': 'KC', 'Kansas City':'KC',
                        'Los Angeles Angels': 'LAA', 'LA Angels':'LAA',
                        'Los Angeles Dodgers': 'LAD', 'LA Dodgers':'LAD',
                        'Miami Marlins':'MIA', 'Miami':'MIA',
                        'Milwaukee Brewers':'MIL', 'Milwaukee':'MIL',
                        'Minnesota Twins':'MIN', 'Minnesota':'MIN',
                        'New York Mets':'NYM', 'NY Mets':'NYM',
                        'New York Yankees':'NYY', 'NY Yankees':'NYY',
                        'Oakland Athletics':'OAK', 'Oakland':'OAK',
                        'Philadelphia Phillies':'PHI', 'Philadelphia':'PHI',
                        'Pittsburgh Pirates':'PIT', 'Pittsburgh':'PIT',
                        'San Diego Padres':'SD', 'San Diego':'SD',
                        'San Francisco Giants': 'SF', 'San Francisco':'SF',
                        'Seattle Mariners':'SEA', 'Seattle':'SEA',
                        'St. Louis Cardinals':'STL', 'St. Louis':'STL',
                        'Tampa Bay Rays':'TB', 'Tampa Bay':'TB',
                        'Texas Rangers':'TEX', 'Texas':'TEX',
                        'Toronto Blue Jays':'TOR', 'Toronto':'TOR',
                        'Washington Nationals':'WAS', 'Washington':'WAS'
                    }
        return fullteams[lookupkey]

    def _validteams(self):
        """
        Valid team lists for the channel.
        """
        validteams = ['BAL', 'BOS', 'LAA', 'CWS', 'CLE',
                    'DET', 'KC', 'MIL', 'MIN', 'NYY', 'OAK',
                    'SEA', 'TEX', 'TOR', 'ATL', 'CHC', 'CIN',
                    'HOU', 'LAD', 'WSH', 'NYM', 'PHI', 'PIT', 
                    'STL', 'SD', 'SF', 'COL', 'MIA', 'ARI', 'TB']

        validteams.sort()

        return validteams

    # display various nba award winners.
    def mlbawards(self, irc, msg, args, optyear):
        """<year>
        Display various MLB awards for current (or previous) year. Use YYYY for year. Ex: 2011
        """

        if not optyear: # crude way to find the latest awards.
            url = 'http://www.baseball-reference.com/awards/'
            req = urllib2.Request(url)
            response = urllib2.urlopen(req)
            html = response.read()
            soup = BeautifulSoup(html) #
            link = soup.find('big', text="Baseball Award Voting Summaries").findNext('a')['href'].strip()
            optyear = ''.join(i for i in link if i.isdigit())

        url = 'http://www.baseball-reference.com/awards/awards_%s.shtml' % optyear
        self.log.info(url)

        try:
            req = urllib2.Request(url)
            response = urllib2.urlopen(req)
            html = response.read()
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

        output = "{0} MLB Awards :: MVP: AL {1} NL {2}  CY: AL {3} NL {4}  ROY: AL {5} NL {6}  MGR: AL {6} NL {7}".format(ircutils.mircColor(optyear, 'red'), \
                ircutils.bold(alvp),ircutils.bold(nlvp),ircutils.bold(alcy),ircutils.bold(nlcy),ircutils.bold(alroy),ircutils.bold(nlroy),ircutils.bold(almgr),ircutils.bold(nlmgr))

        irc.reply(output)

    mlbawards = wrap(mlbawards, [optional('somethingWithoutSpaces')])


    # display upcoming next 5 games.
    def mlbschedule(self, irc, msg, args, optteam):
        """[team]
        Display the last and next five upcoming games for team.
        """

        # needs a translation table: http://sports.yahoo.com/nba/teams
        url = 'http://sports.yahoo.com/mlb/teams/%s/calendar/rss.xml' % optteam

        try:
            req = urllib2.Request(url)
            response = urllib2.urlopen(req)
            html = response.read()
        except:
            irc.reply("Cannot open: %s" % url)
            return

        # clean this stuff up
        html = html.replace('<![CDATA[','') #remove cdata
        html = html.replace(']]>','') # end of cdata
        html = html.replace('EDT','') # tidy up times
        html = html.replace('\xc2\xa0','') # remove some stupid character.

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
            descappend += " [" + date.strip() + "]"
            append_list.append(descappend) # put all into a list.

        self.log.info(str(append_list))

        descstring = string.join([item for item in append_list], " | ")
        output = "{0} {1}".format(ircutils.bold(optteam), descstring)
        irc.reply(output)

    mlbschedule = wrap(mlbschedule, [('somethingWithoutSpaces')])

    def mlbmanager(self, irc, msg, args, optteam):
        """<team>
        Display the manager for team.
        """
        
        # make sure we have a valid team.
        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        # build the url and request.
        url = 'http://espn.go.com/mlb/managers'

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Cannot fetch URL: %s" % url)
            return

        # change some strings to parse better.
        html = html.replace('class="evenrow', 'class="oddrow')

        # soupit.
        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class':'oddrow'})

        object_list = []

        for row in rows:
            manager = row.find('td').find('a')
            exp = manager.findNext('td')
            record = exp.findNext('td')
            team = record.findNext('td').find('a')

            d = collections.OrderedDict()
            d['manager'] = manager.renderContents().strip()
            d['exp'] = exp.renderContents().strip()
            d['record'] = record.renderContents().strip()
            d['team'] = self._fulltoshort(team.renderContents().strip())
            object_list.append(d)
            # done.

        for each in object_list:
            if each['team'] == optteam:
                output = "Manager of {0} is {1}({2}) with {3} years experience.".format(ircutils.bold(each['team']), ircutils.bold(each['manager']), each['record'], each['exp'])
                irc.reply(output)

    mlbmanager = wrap(mlbmanager, [('somethingWithoutSpaces')])

    # alternative: http://erikberg.com/mlb/standings-wildcard.xml
    # http://espn.go.com/mlb/standings/_/type/wild-card
    def mlbstandings(self, irc, msg, args, optlist, optdiv):
        """<ALE|ALC|ALW|NLC|NLC|NLW>
        Display divisional standings for a division.
        """

        # optlist
        expanded, vsdivision = False, False
        for (option, arg) in optlist:
            if option == 'expanded':
                expanded = True
            if option == 'vsdivision':
                vsdivision = True

        # lower the div to match against leaguetable
        optdiv = optdiv.lower()
        leaguetable =   { 
                            'ale': {'league':'American League', 'division':'EAST' },
                            'alc': {'league':'American League', 'division':'CENTRAL' },
                            'alw': {'league':'American League', 'division':'WEST' },
                            'nle': {'league':'National League', 'division':'EAST' },
                            'nlc': {'league':'National League', 'division':'CENTRAL' },
                            'nlw': {'league':'National League', 'division':'WEST' }
                        }

        # sanity check to make sure we have a league.
        if optdiv not in leaguetable:
            irc.reply("League must be one of: %s" % leaguetable.keys())
            return

        # now, go to work.
        if expanded:
            url = 'http://espn.go.com/mlb/standings/_/type/expanded'
        elif vsdivision:
            url = 'http://espn.go.com/mlb/standings/_/type/vs-division'
        else:
            url = 'http://espn.go.com/mlb/standings'

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Problem opening up: %s" % url)
            return
        
        # change to help parsing rows
        html = html.replace('class="evenrow', 'class="oddrow')

        # soup time.
        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class': re.compile('^oddrow*')})

        object_list = []

        for row in rows:
            team = row.find('td', attrs={'align':'left'}).find('a')
            wins = team.findNext('td')
            loss = wins.findNext('td')
            wpct = loss.findNext('td')
            gmsb = wpct.findNext('td')
            home = gmsb.findNext('td')
            road = home.findNext('td')
            rs = road.findNext('td')
            ra = rs.findNext('td')
            diff = ra.findNext('td')
            strk = diff.findNext('td')
            if not vsdivision:
                l10 = strk.findNext('td')
            if not expanded and not vsdivision:
                poff = l10.findNext('td')

            div = row.findPrevious('tr', attrs={'class':'colhead'}).findNext('td', attrs={'align':'left'}) # <tr class="colhead" align="right"><td align="left">

            if vsdivision:
                league = row.findPrevious('tr', attrs={'class':'stathead'}).findNext('td', attrs={'colspan': re.compile('^11')})
            elif expanded:
                league = row.findPrevious('tr', attrs={'class':'stathead'}).findNext('td', attrs={'colspan': re.compile('^12')})
            else:
                league = row.findPrevious('tr', attrs={'class':'stathead'}).findNext('td', attrs={'colspan': re.compile('^13')})

            # now putting into a dict. cleanup.
            d = collections.OrderedDict()
            d['league'] = league.renderContents()
            d['div'] = div.renderContents()
            d['team'] = team.renderContents()
            d['wins'] = wins.renderContents()
            d['loss'] = loss.renderContents()
            d['wpct'] = wpct.renderContents()
            d['gmsb'] = gmsb.renderContents()
            d['home'] = home.renderContents()
            d['road'] = road.renderContents()
            d['rs'] = rs.renderContents()
            d['ra'] = ra.renderContents()
            if expanded or vsdivision:
                d['diff'] = diff.renderContents()
            else:
                d['diff'] = diff.find('span').renderContents()
            d['strk'] = strk.renderContents()
            if not vsdivision:
                d['l10'] = l10.renderContents()
            if not expanded and not vsdivision:
                d['poff'] = poff.renderContents()

            # and add.
            object_list.append(d)

        # time for output.

        # header.
        if expanded:
            header = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:8} {9:8} {10:<7} {11:6}".format( \
                    "Team", "W", "L", "PCT", "GB", "DAY", "NIGHT", "GRASS", "TURF", "1-RUN", "XTRA", "ExWL")
        elif vsdivision:
            header = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:8} {9:8} {10:<7}".format( \
                    "Team", "W", "L", "PCT", "GB", "EAST", "CENT", "WEST", "INTR", "RHP", "LHP")
        else:
            header = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:4} {9:4} {10:<7} {11:6} {12:6}".format( \
                    "Team", "W", "L", "PCT", "GB", "HOME", "ROAD", "RS", "RA", "DIFF", "STRK", "L10", "POFF")

        irc.reply(header)

        # now, each list.

        for tm in object_list:
            if tm['league'] == leaguetable[optdiv].get('league') and tm['div'] == leaguetable[optdiv].get('division'):
                if expanded:
                    output = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:8} {9:8} {10:<7} {11:6}".format( \
                    tm['team'], tm['wins'], tm['loss'], tm['wpct'], tm['gmsb'], tm['home'], tm['road'], tm['rs'], tm['ra'], tm['diff'], tm['strk'], tm['l10'])
                elif vsdivision:
                    output = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:8} {9:8} {10:<7}".format( \
                    tm['team'], tm['wins'], tm['loss'], tm['wpct'], tm['gmsb'], tm['home'], tm['road'], tm['rs'], tm['ra'], tm['diff'], tm['strk'])
                else:
                    output = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:4} {9:4} {10:<7} {11:6} {12:6}".format( \
                    tm['team'], tm['wins'], tm['loss'], tm['wpct'], tm['gmsb'], tm['home'], tm['road'], tm['rs'], tm['ra'], tm['diff'], tm['strk'], tm['l10'], tm['poff']) 

                # output.
                irc.reply(output)

    mlbstandings = wrap(mlbstandings, [getopts({'expanded':'', 'vsdivision':''}), ('somethingWithoutSpaces')])
    
    # display lineups.
    def mlblineup(self, irc, msg, args, optteam):
        """<team>
        Gets lineup for MLB team. Example: NYY
        """

        optteam = optteam.upper()
        
        url = 'http://m.espn.go.com/mlb/lineups?wjb='
        
        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Problem fetching: %s" % url)
            return

        # have to do some replacing for the regex to work
        html = html.replace('<b  >', '<b>')
        html = html.replace('<b>TAM</b>','<b>TB</b>')
        html = html.replace('<b>WAS</b>','<b>WSH</b>')
        html = html.replace('<b>CHW</b>','<b>CWS</b>')

        # dictionary for out.
        outdict = {}

        # regex to find all and put into the dict.
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
            irc.reply("Could not find lineup. Check closer to game time.")
            return

    mlblineup = wrap(mlblineup, [('somethingWithoutSpaces')])

    #23:51 <laburd> @injury cle  returns: player 1, player 2, player 3.. on one line
    #23:51 <laburd> then if you want the injur details you do
    #23:51 <laburd> @injury player
    #23:51 <laburd> It cuts the spam down by an order of magnitude
    
    def mlbinjury(self, irc, msg, args, teamname):
        """<TEAM>
        Show all injuries for team. Example: BOS or NYY
        """

        url = 'http://rotoworld.com/teams/injuries/mlb/%s/' % teamname

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to grab: %s" % url)
            return

        soup = BeautifulSoup(html)

        try:
            team = soup.find('div', attrs={'class': 'player'}).find('a').text
        except:
            irc.reply("Failed to find injuries for: %s" % teamname)
            return

        table = soup.find('table', attrs={'align': 'center', 'width': '600px;'})
        t1 = table.findAll('tr')

        object_list = []

        for row in t1[1:]:
            td = row.findAll('td')
            d = collections.OrderedDict()
            d['name'] = td[0].find('a').text
            d['position'] = td[2].renderContents()
            d['status'] = td[3].renderContents()
            d['date'] = td[4].renderContents().replace("&nbsp;", " ")
            d['injury'] = td[5].renderContents()
            d['returns'] = td[6].renderContents()
            object_list.append(d)

        if len(object_list) < 1:
            irc.reply("No injuries for: %s" % team)

        irc.reply(ircutils.underline(str(team)) + " - " + str(len(object_list)) + " total injuries")
        irc.reply("{0:25} {1:3} {2:6} {3:<7} {4:<15} {5:<10}".format("Name","POS","Status","Date","Injury","Returns"))

        for inj in object_list:
            output = "{0:25} {1:<3} {2:<6} {3:<7} {4:<15} {5:<10}".format(ircutils.bold(inj['name']),inj['position'],inj['status'],inj['date'],inj['injury'],inj['returns'])
            irc.reply(output)

    mlbinjury = wrap(mlbinjury, [('somethingWithoutSpaces')])


    def mlbpowerrankings(self, irc, msg, args):
        """
        Display this week's MLB Power Rankings.
        """
        
        url = 'http://espn.go.com/mlb/powerrankings' 

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
            html = html.replace("evenrow", "oddrow")
        except:
            irc.reply("Failed to fetch: %s" % url)
            return

        # soup it.
        soup = BeautifulSoup(html)

        table = soup.find('table', attrs={'class': 'tablehead'})
        prdate = table.find('td', attrs={'colspan': '6'}).renderContents()

        t1 = table.findAll('tr', attrs={'class': 'oddrow'})

        if len(t1) < 30:
            irc.reply("Failed to parse MLB Power Rankings. Did something break?")
            return

        # object_list for ordereddict.
        object_list = []

        for row in t1:
            rowrank = row.find('td', attrs={'class': 'pr-rank'}).renderContents()
            rowteam = row.find('div', attrs={'style': re.compile('^padding.*')}).find('a').text
            #rowteam = row.find('div', attrs={'style': 'padding\:\s10px\s0px;'}).find('a').text
            rowrecord = row.find('span', attrs={'class': 'pr-record'}).renderContents()
            rowlastweek = row.find('span', attrs={'class': 'pr-last'}).renderContents().replace("Last Week", "prev") 

            # now that we get everything, dump into an ordereddict
            d = collections.OrderedDict()
            d['rank'] = int(rowrank)
            d['team'] = str(rowteam)
            d['record'] = str(rowrecord)
            d['lastweek'] = str(rowlastweek)
            object_list.append(d)

        # one last sanity check.
        if len(object_list) < 30:
            irc.reply("Failed to parse the list. Check your code and formatting.")
            return

        # print the date of Power Rankings
        if prdate:
            irc.reply(ircutils.mircColor(prdate, 'blue'))

        # go through the list, print 6 per line.
        for N in self._grouper(6, object_list, ''):
            irc.reply(' '.join(str(str(n['rank']) + "." + " " + ircutils.bold(n['team'])) + " (" + n['lastweek'] + ")" for n in N))
        

    mlbpowerrankings = wrap(mlbpowerrankings)

    def mlbteamstats(self, irc, msg, args, optteam, optcategory):
        """[TEAM] [category]
        Display team leaders in stats for a specific team in category.
        """

        # we can do year

        optteam = optteam.upper()
        optcategory = optcategory.lower()

        # make sure we have a valid team. Find the tID.
        try:
            tid = self._espntrans(optteam)
        except KeyError:
            irc.reply("Invalid team. Team must be one of %s" % self._validteams())
            return

        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'r':'runs', 'ab':'atBats', 'obp':'onBasePct', 'slug':'slugAvg', 'ops':'OPS', 'sb':'stolenBases', 'runscreated':'runsCreated',
              'w': 'wins', 'l': 'losses', 'win%': 'winPct', 'era': 'ERA',  'k': 'strikeouts', 'k/9ip': 'strikeoutsPerNineInnings', 'holds': 'holds', 's': 'saves',
              'gp': 'gamesPlayed', 'cg': 'completeGames', 'qs': 'qualityStarts', 'whip': 'WHIP' }

        # make sure we have a valid category
        if optcategory not in category:
            irc.reply("Error. Category must be one of: %s" % category.keys())
            return

        # build the url
        url = 'http://m.espn.go.com/mlb/teamstats?teamId=%s&season=2012&lang=EN&category=%s&y=1&wjb=' % (tid, category[optcategory])

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to fetch: %s" % url)
            return


        html = html.replace('<b  >', '<b>')
        html = html.replace('class="ind alt', 'class="ind')
        html = html.replace('class="ind tL', 'class="ind')

        # soup time.
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

    mlbteamstats = wrap(mlbteamstats, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])

    # team leaders. Shows the top 5 teams in a category.
    def mlbteamleaders(self, irc, msg, args, optleague, optcategory):
        """[MLB|AL|NL] [category] 
        Display leaders in category for teams in the MLB.
        Categories: hr, avg, rbi, r, sb, era, whip, k 
        """

        # lower both inputs.
        league = {'mlb': '9', 'al':'7', 'nl':'8'}
        category = {'avg':'avg', 'hr':'homeRuns', 'rbi':'RBIs', 'r':'runs', 'sb':'stolenBases', 'era':'ERA', 'whip':'whip', 'k':'strikeoutsPerNineInnings'}

        optleague = optleague.lower()
        optcategory = optcategory.lower()

        if optleague not in league:
            irc.reply("League must be one of: %s" % league.keys())
            return

        if optcategory not in category:
            irc.reply("Category must be one of: %s" % category.keys())
            return


        url = 'http://m.espn.go.com/mlb/aggregates?category=%s&groupId=%s&y=1&wjb=' % (category[optcategory], league[optleague])

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
            html = html.replace('class="ind alt nw"', 'class="ind nw"')
        except:
            irc.reply("Failed to fetch: %s" % url)
            return

        soup = BeautifulSoup(html)

        try:
            table = soup.find('table', attrs={'class':'table'})
            rows = table.findAll('tr')
        except:
            irc.reply("Could not find a table or rows for mlbteamleaders. Formatting break?")
            return

        append_list = []
        
        for row in rows[1:6]:
            rank = row.find('td', attrs={'class':'ind nw', 'nowrap':'nowrap', 'width':'10%'}).renderContents()
            team = row.find('td', attrs={'class':'ind nw', 'nowrap':'nowrap', 'width':'70%'}).find('a').text
            num = row.find('td', attrs={'class':'ind nw', 'nowrap':'nowrap', 'width':'20%'}).renderContents()
            append_list.append(rank + ". " + team + " " + num)

        thelist = string.join([item for item in append_list], " | ")

        irc.reply("Leaders in %s for %s: %s" % (ircutils.bold(optleague.upper()), ircutils.bold(optcategory.upper()), thelist))

    
    mlbteamleaders = wrap(mlbteamleaders, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])


    def mlbrumors(self, irc, msg, args):
        """
        Display the latest mlb rumors.
        """

        url = 'http://m.espn.go.com/mlb/rumors?wjb='

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
            html = html.replace('<div class="ind alt">', '<div class="ind">') 
        except:
            irc.reply("Something broke trying to read: %s" % url)
            return

        soup = BeautifulSoup(html)

        t1 = soup.findAll('div', attrs={'class': 'ind'})

        if len(t1) < 1:
            irc.reply("No mlb rumors found. Check formatting?")
            return
        for t1rumor in t1[0:7]:
            # dont print <a href="/mlb/
            item = t1rumor.find('div', attrs={'class': 'noborder bold tL'}).renderContents()
            item = re.sub('<[^<]+?>', '', item)
            rumor = t1rumor.find('div', attrs={'class': 'inline rumorContent'}).renderContents().replace('\r','')
            irc.reply(ircutils.bold(item) + " :: " + rumor)

    mlbrumors = wrap(mlbrumors)

    def mlbteamtrans(self, irc, msg, args, optteam):
        """[team]
        Show MLB transactions for [team]. Ex: NYY
        """

        try:
            tid = self._espntrans(optteam)
        except KeyError:
            irc.reply("Invalid team.")
            return

        url = 'http://m.espn.go.com/mlb/teamtransactions?teamId=%s&wjb=' % tid

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read().replace('<div class="ind tL"','<div class="ind"').replace('<div class="ind alt"','<div class="ind"')
        except:
            irc.reply("Failed to load: %s" % url)
            return

        soup = BeautifulSoup(html)

        try:
            t1 = soup.findAll('div', attrs={'class': 'ind'})
        except:
            irc.reply("Parsing broken for: %s" % optteam)
            return

        if len(t1) < 1:
            irc.reply("No transactions found for %s" % optteam)
            return

        for item in t1:
            if "href=" not in str(item):
                trans = item.findAll(text=True)
                irc.reply("{0:8} {1}".format(ircutils.bold(str(trans[0])), str(trans[1])))

    mlbteamtrans = wrap(mlbteamtrans, [('somethingWithoutSpaces')])

    def mlbtrans(self, irc, msg, args, date):
        """[YYYYmmDD]
        Display all mlb transactions. Will only display today's. Use date in format: 20120912
        """

        url = 'http://m.espn.go.com/mlb/transactions?wjb='

        if date:
            try:
                time.strptime(date, '%Y%m%d') # test for valid date
            except:
                irc.reply("ERROR: Date format must be in YYYYMMDD")
                return
        else:
            now = datetime.datetime.now()
            date = now.strftime("%Y%m%d")

        url += '&date=%s' % date

        self.log.info(url)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Something broke trying to read: %s" % url)
            return

        soup = BeautifulSoup(html)
        t1 = soup.findAll('div', attrs={'class': 'ind alt'})
        t1 += soup.findAll('div', attrs={'class': 'ind'})

        # array for out.
        out_array = []

        # loop over.
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
            irc.reply("No transactions on %s" % date)
            return
    
    mlbtrans = wrap(mlbtrans, [optional('somethingWithoutSpaces')])

    def mlbprob(self, irc, msg, args, optdate, optteam):
        """[YYYYMMDD] <TEAM>
        Display the MLB probables for date. Defaults to today. To search
        for a specific team, use their abbr. like NYY
        """

        # without optdate and optteam, we only do a single day (today)
        # with optdate and optteam, show only one date with one team
        # with no optdate and optteam, show whatever the stuff today is.
        # with optdate and no optteam, show all matches that day.

        dates = []
        date = datetime.date.today()
        dates.append(date)

        for i in range(4):
                date += datetime.timedelta(days=1)
                dates.append(date)

        out_array = []

        for eachdate in dates:
                outdate = eachdate.strftime("%Y%m%d")
                url = 'http://m.espn.go.com/mlb/probables?wjb=&date=%s' % outdate # date=20120630&wjb=

                try:
                    req = urllib2.Request(url)
                    html = (urllib2.urlopen(req)).read().replace("ind alt tL spaced", "ind tL spaced")
                except:
                    irc.reply("Failed to load: %s" % url)
                    return

                if "No Games Scheduled" in html:
                    irc.reply("No games scheduled this day.")
                    next

                soup = BeautifulSoup(html)
                t1 = soup.findAll('div', attrs={'class': 'ind tL spaced'})

                for row in t1:
                    matchup = row.find('a', attrs={'class': 'bold inline'}).text.strip()
                    textmatch = re.search(r'<a class="bold inline".*?<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)<br />(.*?)<a class="inline".*?=">(.*?)</a>(.*?)$', row.renderContents(), re.I|re.S|re.M)
                    d = collections.OrderedDict()
                    d['date'] = outdate
                    d['matchup'] = matchup

                    if textmatch:
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
                    irc.reply("{0:25} {1:4} {2:15} {3:12} {4:4} {5:15} {6:12}".format(matchup, vteam, vpitcher,vpstats, hteam, hpitcher, hpstats))

    mlbprob = wrap(mlbprob, [optional('somethingWithoutSpaces'), optional('somethingWithoutSpaces')])

Class = MLB


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=250:
