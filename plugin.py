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
import datetime
import string
import sqlite3
from itertools import izip, groupby, count

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
   
    def _validate(self, date, format):
        """Return true or false for valid date based on format."""
        try:
            datetime.datetime.strptime(date, format) # format = "%m/%d/%Y"
            return True
        except ValueError:
            return False

    def _b64encode(self, string):
        """Returns base64 encoded string."""
        import base64
        return base64.b64encode(string)

    def _b64decode(self, string):
        """Returns base64 encoded string."""
        import base64
        return base64.b64decode(string)
        
    # http://code.activestate.com/recipes/303279/#c7
    def _batch(self, iterable, size):
        c = count()
        for k, g in groupby(iterable, lambda x:c.next()//size):
            yield g

    def _validteams(self):
        """Returns a list of valid teams for input verification."""
        db_filename = self.registryValue('dbLocation')
        with sqlite3.connect(db_filename) as conn:
            cursor = conn.cursor()
            query = "select team from mlb"
            cursor.execute(query)
            teamlist = []
            for row in cursor.fetchall():
                teamlist.append(str(row[0]))

        return teamlist
    
    def _translateTeam(self, db, column, optteam):
        """Translates optteam into proper string using database"""
        db_filename = self.registryValue('dbLocation')
        with sqlite3.connect(db_filename) as conn:
            cursor = conn.cursor()
            query = "select %s from mlb where %s='%s'" % (db, column, optteam)
            self.log.info(query)
            cursor.execute(query)
            row = cursor.fetchone()
            
            return (str(row[0]))

    def mlbteams(self, irc, msg, args):
        """Display a list of valid teams for input."""
        
        teams = self._validteams()        
        irc.reply("Valid teams are: %s" % (string.join([item for item in teams], " | ")))

    mlbteams = wrap(mlbteams)
    
    def baseball(self, irc, msg, args):
        """Display a silly baseball."""
    
        irc.reply("    ____     ")
        irc.reply("  .'    '.   ")
        irc.reply(" /"+ircutils.mircColor("'-....-'", 'red') + "\  ")
        irc.reply(" |        |  ")
        irc.reply(" \\"+ircutils.mircColor(".-''''-.", 'red') + "/  ")
        irc.reply("  '.____.'   ")
    
    baseball = wrap(baseball)
    
    def mlbvaluations(self, irc, msg, args):
        """Display current MLB team valuations from Forbes."""
        
        url = 'http://www.forbes.com/mlb-valuations/list/'

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
            irc.reply(' '.join(str(str(n['rank']) + "." + " " + ircutils.bold(n['team'])) + " (" + n['value'] + ")" for n in N))        
            
    mlbvaluations = wrap(mlbvaluations)

    def mlbplayoffs(self, irc, msg, args):
        """Display playoff matchups if season ended today."""
    
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9odW50Zm9yb2N0b2Jlcg==')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply('Failed to fetch: %s' % (self._b64decode('url')))
            return
        
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
        self.log.info(url)

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

        self.log.info(str(len(rows)))

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
                 
    # mlbscores. use gd2 (gameday) data.
    def mlbscores(self, irc, msg, args, optdate):
        """[date]
        Display current MLB scores.
        """
        
        import xmltodict
        
        if optdate: 
            testdate = self._validate(optdate, '%Y%m%d')
            if not testdate:
                irc.reply("Invalid year. Must be YYYYmmdd.")
                return
            else:
                _year = optdate[0:4]
                _month = optdate[4:6]
                _day = optdate[6:8]
        else:
            (_month, _day, _year) = datetime.date.today().strftime("%m/%d/%Y").split('/')
        
        url = 'http://gd2.mlb.com/components/game/mlb/year_%s/month_%s/day_%s/miniscoreboard.xml' % (_year, _month, _day)
        self.log.info(url)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to fetch: %s" % url)
            return

        doc = xmltodict.parse(html)
        games = doc['games']['game'] # always there.
        
        if len(games) < 1:
            irc.reply("We failed to find any games for that day")
            return

        object_list = []

        for each in games:
            d = collections.OrderedDict()
            d['outs'] = str(each.get('@outs', None))
            d['top_inning'] = str(each.get('@top_inning', None))
            d['inning'] = str(each.get('@inning', None))
            d['awayteam'] = str(each.get('@away_name_abbrev', None))
            d['hometeam'] = str(each.get('@home_name_abbrev', None))
            d['awayruns'] = str(each.get('@away_team_runs', None))
            d['homeruns'] = str(each.get('@home_team_runs', None))
            d['time'] = str(each.get('@time', None))
            d['ampm'] = str(each.get('@ampm', None))
            d['status'] = str(each.get('@status', None))
            object_list.append(d)

        #for each in object_list:
         
    mlbscores = wrap(mlbscores, [optional('somethingWithoutSpaces')])

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
        """<--expanded|--vsdivision> [ALE|ALC|ALW|NLC|NLC|NLW]
        Display divisional standings for a division. Use --expanded or --vsdivision
        to show extended stats.
        """

        expanded, vsdivision = False, False
        for (option, arg) in optlist:
            if option == 'expanded':
                expanded = True
            if option == 'vsdivision':
                vsdivision = True

        optdiv = optdiv.lower()
        leaguetable =   { 
                            'ale': {'league':'American League', 'division':'EAST' },
                            'alc': {'league':'American League', 'division':'CENTRAL' },
                            'alw': {'league':'American League', 'division':'WEST' },
                            'nle': {'league':'National League', 'division':'EAST' },
                            'nlc': {'league':'National League', 'division':'CENTRAL' },
                            'nlw': {'league':'National League', 'division':'WEST' }
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
        
        html = html.replace('class="evenrow', 'class="oddrow')

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

            div = row.findPrevious('tr', attrs={'class':'colhead'}).findNext('td', attrs={'align':'left'}) 

            if vsdivision:
                league = row.findPrevious('tr', attrs={'class':'stathead'}).findNext('td', attrs={'colspan': re.compile('^11')})
            elif expanded:
                league = row.findPrevious('tr', attrs={'class':'stathead'}).findNext('td', attrs={'colspan': re.compile('^12')})
            else:
                league = row.findPrevious('tr', attrs={'class':'stathead'}).findNext('td', attrs={'colspan': re.compile('^13')})

            d = collections.OrderedDict()
            d['league'] = league.renderContents().strip()
            d['div'] = div.renderContents().strip()
            d['team'] = team.renderContents().strip()
            d['wins'] = wins.renderContents().strip()
            d['loss'] = loss.renderContents().strip()
            d['wpct'] = wpct.renderContents().strip()
            d['gmsb'] = gmsb.renderContents().strip()
            d['home'] = home.renderContents().strip()
            d['road'] = road.renderContents().strip()
            d['rs'] = rs.renderContents().strip()
            d['ra'] = ra.renderContents().strip()
            if expanded or vsdivision:
                d['diff'] = diff.renderContents().strip()
            else:
                d['diff'] = diff.find('span', text=True)
            d['strk'] = strk.renderContents().strip()
            if not vsdivision:
                d['l10'] = l10.renderContents().strip()
            if not expanded and not vsdivision:
                d['poff'] = poff.renderContents().strip()

            object_list.append(d)

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

        for tm in object_list:
            if tm['league'] == leaguetable[optdiv].get('league') and tm['div'] == leaguetable[optdiv].get('division'):
                if expanded:
                    output = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:8} {9:8} {10:<7} {11:6}".format( \
                    tm['team'], tm['wins'], tm['loss'], tm['wpct'], tm['gmsb'], tm['home'], tm['road'], tm['rs'], \
                    tm['ra'], tm['diff'], tm['strk'], tm['l10'])
                elif vsdivision:
                    output = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:8} {9:8} {10:<7}".format( \
                    tm['team'], tm['wins'], tm['loss'], tm['wpct'], tm['gmsb'], tm['home'], tm['road'], tm['rs'], \
                    tm['ra'], tm['diff'], tm['strk'])
                else:
                    output = "{0:15} {1:3} {2:3} {3:5} {4:5} {5:8} {6:8} {7:4} {8:4} {9:4} {10:<7} {11:6} {12:6}".format( \
                    tm['team'], tm['wins'], tm['loss'], tm['wpct'], tm['gmsb'], tm['home'], tm['road'], tm['rs'], \
                    tm['ra'], tm['diff'], tm['strk'], tm['l10'], tm['poff']) 

                irc.reply(output)

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
            irc.reply("Could not find lineup. Check closer to game time.")
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
        """[YYYYMMDD] <TEAM>
        Display the MLB probables for date. Defaults to today. To search
        for a specific team, use their abbr. like NYY
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

            # fix some teams here. stupid espn.
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
                    irc.reply("{0:25} {1:4} {2:15} {3:12} {4:4} {5:15} {6:12} {7:10}".format(eachentry['matchup'], eachentry['vteam'], \
                        eachentry['vpitcher'],eachentry['vpstats'], eachentry['hteam'], eachentry['hpitcher'], eachentry['hpstats'], eachentry['date']))

    mlbprob = wrap(mlbprob, [optional('somethingWithoutSpaces')])

Class = MLB


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=250:
