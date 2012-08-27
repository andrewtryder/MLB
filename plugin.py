# -*- coding: utf-8 -*-
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
import time
import string
import sqlite3
from itertools import izip, groupby, count
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
   
    def _validate(self, date, format):
        """Return true or false for valid date based on format."""
        try:
            datetime.datetime.strptime(date, format) # format = "%m/%d/%Y"
            return True
        except ValueError:
            return False


    def _smart_truncate(self, text, length, suffix='...'):
        """Truncates `text`, on a word boundary, as close to
        the target length it can come.
        """

        slen = len(suffix)
        pattern = r'^(.{0,%d}\S)\s+\S+' % (length-slen-1)
        if len(text) > length:
            match = re.match(pattern, text)
            if match:
                length0 = match.end(0)
                length1 = match.end(1)
                if abs(length0+slen-length) < abs(length1+slen-length):
                    return match.group(0) + suffix
                else:
                    return match.group(1) + suffix
        return text


    def _shortenUrl(self, url):
        """Returned goo.gl shortened URL."""
        posturi = "https://www.googleapis.com/urlshortener/v1/url"
        headers = {'Content-Type' : 'application/json'}
        data = {'longUrl' : url}
        data = json.dumps(data)
        request = urllib2.Request(posturi,data,headers)
        response = urllib2.urlopen(request)
        response_data = response.read()
        shorturi = json.loads(response_data)['id']
        return shorturi


    def _b64decode(self, string):
        """Returns base64 decoded string."""
        import base64
        return base64.b64decode(string)

    def _daysSince(self, string):
        a = datetime.date.today()
        b = datetime.datetime.strptime(string, "%B %d, %Y")
        b = b.date()
        delta = b - a
        delta = abs(delta.days)
        return delta

        
    def _dateFmt(self, string):
        """Return a short date string from a full date string."""
        return time.strftime('%m/%d', time.strptime(string, '%B %d, %Y'))
        
        
    def _batch(self, iterable, size):
        c = count()
        for k, g in groupby(iterable, lambda x:c.next()//size):
            yield g

    
    def _millify(self, num):
        for x in ['','k','M','B','T']:
            if num < 1000.0:
              return "%3.1f%s" % (num, x)
            num /= 1000.0
            

    def _salary(self, flags):
        """http://developer.usatoday.com/docs/read/salaries"""

        apiKey = self.registryValue('usatApiKey')
        if not apiKey or apiKey == "Not set":
            self.log.info("API key not set. see 'config help plugins.MLB.USATapiKey'.")
            return

        jsonurl = 'http://api.usatoday.com/open/salaries/mlb?%s' % (flags)
        jsonurl += '&encoding=json'
        jsonurl += '&api_key=%s' % (apiKey)

        self.log.info(jsonurl)

        try:
            request = urllib2.Request(jsonurl)
            response = urllib2.urlopen(request)
            response_data = response.read()
        except urllib2.HTTPError as err:
            if err.code == 404:
                irc.reply("Error 404")
                self.log.warning("Error 404 on: %s" % (jsonurl))
            elif err.code == 403:
                irc.reply("Error 403. Try waiting 60 minutes.")
                self.log.warning("Error 403 on: %s" %s (jsonurl))
            else:
                irc.reply("Error. Check the logs.")
            return

        return response_data
        

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
            #self.log.info(query)
            cursor.execute(query)
            row = cursor.fetchone()
            
            return (str(row[0]))
    
    
    ###################################
    # Public Functions.
    ###################################
    
    
    def mlballstargame(self, irc, msg, args, optyear):
        """[YYYY]
        Display results for that year's MLB All-Star Game. Ex: 1996. Earliest year is 1933 and latest is this season.
        """
        
        testdate = self._validate(optyear, '%Y')
        if not testdate:
            irc.reply("Invalid year. Must be YYYY.")
            return
        
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9hbGxzdGFyZ2FtZS9oaXN0b3J5')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        soup = BeautifulSoup(html)
        rows = soup.findAll('tr', attrs={'class':re.compile('^evenrow|^oddrow')})

        allstargames = collections.defaultdict(list)

        for row in rows:
            tds = row.findAll('td')
            year, score, location, attendance, mvp = tds[0], tds[1], tds[2], tds[4], tds[3]
            appendString = str("Score: " + score.getText() + "  Location: " + location.getText() + "  Attendance: " + attendance.getText() + "  MVP: " + mvp.getText())
            allstargames[str(year.getText())].append(appendString)

        outyear = allstargames.get(optyear, None)
        
        if not outyear:
            irc.reply("I could not find MLB All-Star Game information for: %s" % optyear)
            return
        else:
            output = "{0} All-Star Game :: {1}".format(ircutils.bold(optyear), "".join(outyear))
            irc.reply(output)
    
    mlballstargame = wrap(mlballstargame, [('somethingWithoutSpaces')])
    
    
    def mlbcyyoung(self, irc, msg, args):
        """
        Display Cy Young prediction list. Uses a method, based on past results, to predict Cy Young balloting.
        """
        
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9mZWF0dXJlcy9jeXlvdW5n')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
        
        html = html.replace('&amp;','&').replace('ARZ','ARI').replace('CHW','CWS').replace('WAS','WSH').replace('MLW','MIL')
            
        soup = BeautifulSoup(html)
        players = soup.findAll('tr', attrs={'class':re.compile('(^oddrow.*?|^evenrow.*?)')})

        cyyoung = collections.defaultdict(list)

        for player in players:
            colhead = player.findPrevious('tr', attrs={'class':'stathead'}) 
            rank = player.find('td')
            playerName = rank.findNext('td')
            team = playerName.findNext('td')
            appendString = str(rank.getText() + ". " + ircutils.bold(playerName.getText()) + " (" + team.getText() + ")")
            cyyoung[str(colhead.getText())].append(appendString)

        for i,x in cyyoung.iteritems():
            descstring = string.join([item for item in x], " | ")
            output = "{0} :: {1}".format(ircutils.mircColor(i, 'red'), descstring)
            irc.reply(output)
        
    mlbcyyoung = wrap(mlbcyyoung)
    
    
    def mlbseries(self, irc, msg, args, optteam, optopp):
        """[team] [opp]
        Display the remaining games between TEAM and OPP in the current schedule. Ex: NYY TOR
        """
        
        optteam,optopp = optteam.upper(),optopp.upper()
        
        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return
        
        if optopp not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        currentYear = str(datetime.date.today().year) # need as a str.
        
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtcy9wcmludFNjaGVkdWxlL18vdGVhbQ==') + '/%s/season/%s' % (optteam, currentYear)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        soup = BeautifulSoup(html) # the html here is junk/garbage. soup cleans this up, even if using a regex. 

        append_list, out_list = [], []

        schedRegex = '<tr><td><font class="verdana" size="1"><b>(.*?)</b></font></td><td><font class="verdana" size="1">(.*?)</font></td>.*?<td align="right"><font class="verdana" size="1">(.*?)</font></td></tr>'
        
        patt = re.compile(schedRegex, re.I|re.S|re.M) # ugh, regex was the only way due to how horrible the printSchedule is. 

        for m in patt.finditer(str(soup)):
            mDate, mOpp, mTime = m.groups()
            mDate = mDate.replace('.','').replace('Sept','Sep') # replace the at and Sept has to be fixed for %b
            if "at " in mOpp: # clean-up the opp and shorten. 
                mOpp = self._translateTeam('team', 'ename', mOpp.replace('at ','').strip())
                mOpp = "@" + mOpp
            else:
                mOpp = self._translateTeam('team', 'ename', mOpp.strip())
            if datetime.datetime.strptime(mDate + " " + currentYear, '%b %d %Y').date() >= datetime.date.today(): # only show what's after today
                append_list.append(mDate + " - " + ircutils.bold(mOpp) + " " + mTime)

        for each in append_list: # here, we go through all remaining games, only pick the ones with the opp in it, and go from there.
            if optopp in each: # this is real cheap using string matching instead of assigning keys, but easier. 
                out_list.append(each)

        if len(out_list) > 0:
            descstring = string.join([item for item in out_list], " | ")
            output = "There are {0} games between {1} and {2} :: {3}".format(ircutils.mircColor(len(out_list), 'red'), ircutils.bold(optteam), ircutils.bold(optopp), descstring)
            irc.reply(output)
        else:
            irc.reply("I do not see any remaining games between: {0} and {1} in the {2} schedule.".format(ircutils.bold(optteam), ircutils.bold(optopp), currentYear))
        
    mlbseries = wrap(mlbseries, [('somethingWithoutSpaces'), ('somethingWithoutSpaces')])
    
    
    def mlbejections(self, irc, msg, args):
        """Display the total number of ejections and five most recent
        for the MLB season.
        """
        
        url = self._b64decode('aHR0cDovL3BvcnRhbC5jbG9zZWNhbGxzcG9ydHMuY29tL21sYi1lamVjdGlvbi1saXN0')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        soup = BeautifulSoup(html)
        ejectedTotal = soup.find('div', attrs={'class':'sites-list-showing-items'}).find('span')
        table = soup.find('table', attrs={'id':'goog-ws-list-table', 'class':'sites-table goog-ws-list-table'})
        rows = table.findAll('tr')[1:6] # last 5. header row is 0.

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
            date = str(self._dateFmt(date.getText()))
    
            append_list.append(date + " - " + str(umpname.getText()) + " ejected " + str(ejected.getText()) + "(" + str(ejpos.getText()) + ")")
        
        descstring = string.join([item for item in append_list], " | ")         
        output = "There have been %s ejections this season. Last five:" % (ircutils.underline(ejectedTotal.getText()))    
    
        irc.reply("{0} {1}".format(output, descstring))
    
    mlbejections = wrap(mlbejections)
    

    def mlbarrests(self, irc, msg, args):
        """
        Display the last 5 MLB arrests.
        """    
    
        url = self._b64decode('aHR0cDovL2FycmVzdG5hdGlvbi5jb20vY2F0ZWdvcnkvcHJvLWJhc2ViYWxsLw==')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        html = html.replace('&nbsp;',' ').replace('&#8217;','’')

        soup = BeautifulSoup(html)
        lastDate = soup.findAll('span', attrs={'class':'time'})[0] 
        divs = soup.findAll('div', attrs={'class':'entry'})

        append_list = []

        for div in divs:
            title = div.find('h2')
            datet = div.find('span', attrs={'class':'time'})
            datet = self._dateFmt(str(datet.getText()))
            arrestedFor = div.find('strong', text=re.compile('Team:'))    
            if arrestedFor:
                matches = re.search(r'<strong>Team:.*?</strong>(.*?)<br />', arrestedFor.findParent('p').renderContents(), re.I|re.S|re.M)
                if matches:
                    college = matches.group(1).replace('(MLB)','').strip()
                else:
                    college = "None"
            else:
                college = "None"
            
            append_list.append(ircutils.bold(datet) + " :: " + title.getText() + " - " + college) # finally add it all
        
        daysSince = self._daysSince(str(lastDate.getText()))
        irc.reply("{0} days since last MLB arrest".format(ircutils.mircColor(daysSince, 'red')))
        
        for each in append_list[0:6]:
            irc.reply(each)

    mlbarrests = wrap(mlbarrests)
    
    
    def mlbstats(self, irc, msg, args, optlist, optplayer):
        """<--year YYYY> [player name]
        Display career totals and season averages for player. If --year YYYY is
        specified, it will display the season stats for that player, if available.
        NOTE: This command is intended for retired/inactive players, not active ones.
        """

        (first, last) = optplayer.split(" ", 1) #playername needs to be "first-last"
        searchplayer = first + '-' + last

        optyear = False
        for (option, arg) in optlist:
            if option == 'year':
                optyear = arg
        
        url = self._b64decode('aHR0cDovL3NlYXJjaC5lc3BuLmdvLmNvbS8=') + '%s' % searchplayer
        
        #self.log.info(url)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
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
            #if playercard.find('a', attrs={'href':re.compile('.*?espn.go.com/mlb/players/stats.*?')}):
            link = playercard.find('a', attrs={'href':re.compile('.*?espn.go.com/mlb/players/stats.*?')})['href']
        
        if not link:
            irc.reply("I didn't find the link I needed for career stats. Did something break?")
            return
        else:
            try:
                req = urllib2.Request(link)
                html = (urllib2.urlopen(req)).read()
            except:
                irc.reply("Failed to open: %s" % link)
                return
                
        soup = BeautifulSoup(html)
        playerName = soup.find('title')
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
                outyear = string.join([item for item in outyear], " | ")
                irc.reply("{0} :: {1}".format(optplayer,outyear))               
        else:
            endrows = table.findAll('tr', attrs={'class':re.compile('^evenrow bi$|^oddrow bi$')})
    
            for total in endrows:
                if total.find('td', text="Total"):
                    totals = total.findAll('td')
                if total.find('td', text="Season Averages"):
                    seasonaverages = total.findAll('td')
    
            del seasonaverages[0] #remove the first td, but match up header via j+2
            del totals[0:2]

            seasonstring = string.join([header[i+2].getText() + ": " + td.getText() for i,td in enumerate(seasonaverages)], " | ")
            totalstring = string.join([header[i+2].getText() + ": " + td.getText() for i,td in enumerate(totals)], " | ")
            
            irc.reply("{0} Season Averages :: {1}".format(ircutils.bold(optplayer), seasonstring))
            irc.reply("{0} Career Totals :: {1}".format(ircutils.bold(optplayer), totalstring))
    
    mlbstats = wrap(mlbstats, [(getopts({'year':('int')})), ('text')])
    
    def mlbgamesbypos (self, irc, msg, args, optteam):
        """[team]
        Display a team's games by position. Ex: NYY
        """

        optteam = optteam.upper()
        
        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return

        if optteam == 'CWS': # didn't want a new table here for one site, so this is a cheap stop-gap. 
            optteam = 'chw'
        else:
            optteam = optteam.lower()
            
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi90ZWFtL2xpbmV1cC9fL25hbWU=') + '/%s/' % optteam

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        soup = BeautifulSoup(html)

        table = soup.find('td', attrs={'colspan':'2'}, text="GAMES BY POSITION").findParent('table')
        rows = table.findAll('tr', attrs={'class':re.compile('oddrow|evenrow')})

        append_list = []

        for row in rows:
            playerPos = row.find('td').find('strong')
            playersList = playerPos.findNext('td')
            append_list.append(str(ircutils.bold(playerPos.getText()) + " " + playersList.getText()))

        descstring = string.join([item for item in append_list], " | ") 
        output = "{0} :: {1}".format(ircutils.underline(optteam.upper()), descstring)
        
        irc.reply(output)

    mlbgamesbypos = wrap(mlbgamesbypos, [('somethingWithoutSpaces')])
    
    
    def mlbroster(self, irc, msg, args, optlist, optteam):
        """<--40man|--active> [team]
        Display active roster for team. Defaults to active roster but use --40man switch to 
        show the entire roster. Ex: --40man NYY
        """

        optteam = optteam.upper()
        
        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
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

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        html = html.replace('class="evenrow','class="oddrow')

        soup = BeautifulSoup(html)
        table = soup.find('div', attrs={'class':'mod-content'}).find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr', attrs={'class':re.compile('oddrow player.*?')})

        team_data = collections.defaultdict(list)
        
        for row in rows:
            playerType = row.findPrevious('tr', attrs={'class':'stathead'})     
            playerNum = row.find('td')
            playerName = playerNum.findNext('td').find('a')
            playerPos = playerName.findNext('td')
            team_data[str(playerType.getText())].append(str(playerName.getText() + " (" + playerPos.getText() + ")"))

        for i,j in team_data.iteritems():
            output = "{0} {1} :: {2}".format(ircutils.underline(optteam.upper()), ircutils.bold(i), string.join([item for item in j], " | "))
            irc.reply(output)
    
    mlbroster = wrap(mlbroster, [getopts({'active':'','40man':''}), ('somethingWithoutSpaces')])
    
    
    def mlbrosterstats(self, irc, msg, args, optteam):
        """<team>
        Displays top 5 youngest/oldest teams. Optionally, use TEAM as argument to display
        roster stats/averages for MLB team. Ex: NYY
        """

        if optteam:
            optteam = optteam.upper()
            if optteam not in self._validteams():
                irc.reply("Team not found. Must be one of: %s" % self._validteams())
                return
        
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi9zdGF0cy9yb3N0ZXJz')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'class':'tablehead'})
        rows = table.findAll('tr')[2:]

        object_list = []

        for row in rows:
            rank = row.find('td')
            team = rank.findNext('td')
            rhb = team.findNext('td')
            lhb = rhb.findNext('td')
            sh = lhb.findNext('td')
            rhp = sh.findNext('td')
            lhp = rhp.findNext('td')
            ht = lhp.findNext('td')
            wt = ht.findNext('td')
            age = wt.findNext('td')
            young = age.findNext('td')
            old = young.findNext('td')
            
            aString = str("RHB: " + rhb.getText() + "  LHB: " + lhb.getText() + "  SH: " + sh.getText() + "  RHP: " + rhp.getText() + "  LHP: " + lhp.getText()\
                + "  AVG HT: " + ht.getText() + "  AVG WEIGHT: " + wt.getText() + "  AVG AGE: " + age.getText() + "  YOUNGEST: " + young.getText() + "  OLDEST: " + old.getText())
            
            d = collections.OrderedDict()
            d['team'] = str(self._translateTeam('team', 'ename', team.getText()))
            d['data'] = str(aString)
            object_list.append(d)
        
        if optteam:
            for each in object_list:
                if each['team'] == optteam: # list will have all teams so we don't need to check
                    output = "{0} Roster Stats :: {1}".format(ircutils.bold(each['team']), each['data'])
            
            irc.reply(output)
            
        else:
            
            youngest_list = []
            oldest_list = []
            
            for each in object_list[0:5]:
                youngest_list.append(each['team'])
            for each in object_list[-6:-1]:
                oldest_list.append(each['team'])
            
            output = "{0} :: {1}".format(ircutils.bold("5 Youngest MLB Teams:"), string.join([item for item in youngest_list], " | "))
            irc.reply(output)
            
            output = "{0} :: {1}".format(ircutils.bold("5 Oldest MLB Teams:"), string.join([item for item in oldest_list], " | "))
            irc.reply(output)           
    
    mlbrosterstats = wrap(mlbrosterstats, [optional('somethingWithoutSpaces')])


    def mlbteamsalary(self, irc, msg, args, optteam):
        """[team]
        Display top 5 salaries for teams. Ex: Yankees
        """
        
        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return
            
        lookupteam = self._translateTeam('short', 'team', optteam) # (db, column, optteam)

        flags = 'seasons=%s&teams=%s' % (datetime.datetime.now().year, lookupteam)

        response_data = self._salary(flags)        
        jsondata = json.loads(response_data)

        if len(jsondata['salaries']) < 1:
            irc.reply("I did not find any team salary data in %s for %s" % (sportname, team))
            return

        salaryAverage = str(jsondata['salaries'][0]['average']).replace(",","")
        salaryMed = str(jsondata['salaries'][0]['med']).replace(",","")
        salaryStdev = str(jsondata['salaries'][0]['stdev']).replace(",","")
        salaryTotal = str(jsondata['salaries'][0]['total']).replace(",","")

        s = jsondata['salaries'][0]['salary']
        ln = lambda x: int(x.get('salary').replace(",",""))
        esorted = sorted(s, key=ln,reverse=True)

        output = ircutils.bold(ircutils.underline(optteam))
        output += " " + "Average: " + self._millify(int(salaryAverage))
        output += " " + "Median: " + self._millify(int(salaryMed))
        output += " " + "Total: " + self._millify(int(salaryTotal))

        salString = ircutils.bold(ircutils.underline(optteam)) + " (top 5 salary): "

        for i,entry in enumerate(esorted):
            if i < 6:
                salaryEntry = self._millify(int(entry['salary'].replace(",","")))
                salString += salaryEntry + " " + entry['player_full_name'] + "(" + entry['position'] + ") " 

        irc.reply(output)
        irc.reply(salString)

    mlbteamsalary = wrap(mlbteamsalary, [('text')])
    
    # top5 paid players: http://api.usatoday.com/open/salaries/mlb?players=&top=5&seasons=2012
    
    def mlbsalary(self, irc, msg, args, optplayer):
        """[player]
        Get the last 4 years of salary for player name. Ex: Derek Jeter
        """
        
        flags='players=%s' % (optplayer.replace(" ","-").strip())

        response_data = self._salary(flags)
        jsondata = json.loads(response_data)

        length = jsondata.get('salaries', None)[0]

        if length is None:
            irc.reply("No salary data found for: %s" % optplayer)
            return

        seasons = jsondata['rootmetadata'][0]['seasons']
        currentSeason = jsondata['rootmetadata'][0]['currentSeason']
        salaryAverage = jsondata['salaries'][0]['average'] # here
        salaryMedian = jsondata['salaries'][0]['med']
        
        s = jsondata['salaries'][0]['salary']
        ln = lambda x: x.get('season')
        esorted = sorted(s, key=ln,reverse=True)

        salString = string.join([i['season']+": "+ self._millify(int(i['salary'].replace(",",""))) for i in esorted], " | ")
        irc.reply(ircutils.bold(optplayer.title()) + ": " + salString)

    mlbsalary = wrap(mlbsalary, [('text')])
    
    
    def mlbffplayerratings(self, irc, msg, args, optposition):
        """<position>
        Display MLB player ratings per position. Positions must be one of:
        Batters | Pitchers | C | 1B | 2B | 3B | SS | 2B/SS | 1B/3B | OF | SP | RP
        """
                
        validpositions = { 'Batters':'?&slotCategoryGroup=1','Pitchers':'?&slotCategoryGroup=2', 'C':'?&slotCategoryId=0', '1B':'?&slotCategoryId=1', 
            '2B':'?&slotCategoryId=2', '3B':'?&slotCategoryId=3', 'SS':'?&slotCategoryId=4', '2B/SS':'?&slotCategoryId=6', '1B/3B':'?&slotCategoryId=7',
            'OF':'?&slotCategoryId=5', 'SP':'?&slotCategoryId=14', 'RP':'?&slotCategoryId=15' }
        
        if optposition and optposition not in validpositions:
            irc.reply("Invalid position. Must be one of: %s" % validpositions.keys())
            return
            
        url = self._b64decode('aHR0cDovL2dhbWVzLmVzcG4uZ28uY29tL2ZsYi9wbGF5ZXJyYXRlcg==')

        if optposition:
            url += '%s' % validpositions[optposition]
        
        self.log.info(url)
        
        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
            
        html = html.replace('&nbsp;',' ')
    
        soup = BeautifulSoup(html)
        table = soup.find('table', attrs={'id':'playertable_0'})
        rows = table.findAll('tr')[2:12]

        append_list = []

        for row in rows:
            rank = row.find('td')
            player = row.find('td', attrs={'class':'playertablePlayerName'}).find('a')
            rating = row.find('td', attrs={'class':'playertableData sortedCell'})
            append_list.append(rank.getText() + ". " + ircutils.bold(player.getText()) + " (" + rating.getText() + ")")
    
        descstring = string.join([item for item in append_list], " | ") 

        if optposition:
            title = "Top 10 FF projections at: %s" % optposition
        else:
            title = "Top 10 FF projections"
            
        output = "{0} :: {1}".format(ircutils.mircColor(title, 'red'), descstring)
        irc.reply(output)
        
    mlbffplayerratings = wrap(mlbffplayerratings, [optional('somethingWithoutSpaces')])
    
    
    def mlbwar(self, irc, msg, args, opttype):
        """[overall|pitching|offense|fielding]
        Display MLB leaders in WAR for various categories.
        """
        
        opttype = opttype.lower()
        
        wartypelist = ['overall','pitching','offense','fielding']
        
        if opttype not in wartypelist:
            irc.reply("WAR type must be one of: %s" % wartypelist)
            return
            
        url = self._b64decode('aHR0cDovL2VzcG4uZ28uY29tL21sYi8=')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except: 
            irc.reply("Failed to open: %s" % url)
            return
                
        soup = BeautifulSoup(html)
        regexString = 'war' + opttype + '.*?' # build regex ourselves for searching.
        div = soup.find('div', attrs={'id':re.compile(regexString)})

        table = div.find('table')
        rows = table.findAll('tr')[1:] # skip header.

        append_list = []

        for row in rows:
            rank = row.find('td')
            player = rank.findNext('td')
            team = player.findNext('td')
            war = team.findNext('td')
            append_list.append(ircutils.bold(player.getText()) + " (" + team.getText() + ") " + war.getText())

        descstring = string.join([item for item in append_list], " | ")
        output = "{0} {1} :: {2}".format(ircutils.mircColor("WAR Leaders for:", 'red'), ircutils.underline(opttype.title()), descstring)
        
        irc.reply(output)
    
    mlbwar = wrap(mlbwar, [('somethingWithoutSpaces')])

        
    def mlbteamnews(self, irc, msg, args, optteam):
        """[team]
        Display the most recent news and articles about a team. Ex: NYY
        """

        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return
            
        lookupteam = self._translateTeam('fanfeedr', 'team', optteam) # (db, column, optteam)

        apiKey = self.registryValue('ffApiKey')
        if not apiKey or apiKey == "Not set":
            irc.reply("API key not set. see 'config help supybot.plugins.MLB.ffApiKey'.")
            return
        
        url = 'http://ffapi.fanfeedr.com/basic/api/teams/%s/content' % lookupteam
        url += '?api_key=%s' % apiKey #
        
        self.log.info(url)

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
        
        try:
            jsondata = json.loads(html)
        except:
            irc.reply("Could not parse json data")
            return
            
        for each in jsondata[0:6]:
            origin = each['origin']['name']
            title = each['title']
            linkurl = each['url']
            output = "{0} - {1} {2}".format(ircutils.underline(origin), self._smart_truncate(title, 40),\
                ircutils.mircColor(self._shortenUrl(linkurl), 'blue'))
            irc.reply(output)

    mlbteamnews = wrap(mlbteamnews, [('somethingWithoutSpaces')])

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
    

    def mlbweather(self, irc, msg, args, optteam):
        """[team]
        Display weather for MLB team at park they are playing at.
        """
        
        optteam = optteam.upper().strip()

        if optteam not in self._validteams():
            irc.reply("Team not found. Must be one of: %s" % self._validteams())
            return
        
        url = self._b64decode('aHR0cDovL3d3dy5wYXJrZmFjdG9ycy5jb20v')

        try:
            req = urllib2.Request(url)
            html = (urllib2.urlopen(req)).read()
        except:
            irc.reply("Failed to open: %s" % url)
            return
        
        if "an error occurred while processing this directive" in html:
            irc.reply("Something broke with parkfactors. Check back later.")
            return
            
        html = html.replace('&amp;','&').replace('ARZ','ARI').replace('CHW','CWS').replace('WAS','WSH').replace('MLW','MIL') # need some mangling.

        soup = BeautifulSoup(html)
        h3s = soup.findAll('h3')

        object_list = []

        for h3 in h3s:
            park = h3.find('span', attrs={'style':'float: left;'})
            factor = h3.find('span', attrs={'style': re.compile('color:.*?')})
            matchup = h3.findNext('h4').find('span', attrs={'style':'float: left;'})
            winddir = h3.findNext('img', attrs={'class':'rose'})
            windspeed = h3.findNext('p', attrs={'class':'windspeed'}).find('span')
            weather = h3.findNext('h5', attrs={'class':'l'})
            if weather.find('img', attrs={'src':'../images/roof.gif'}):
                weather = "[ROOF] " + weather.text 
            else:
                weather = weather.text.strip()

            d = collections.OrderedDict()
            d['park'] = park.renderContents().strip()
            d['factor'] = factor.renderContents().strip()
            d['matchup'] = matchup.renderContents().strip()
            d['winddir'] = str(''.join(i for i in winddir['src'] if i.isdigit()))
            d['windspeed'] = windspeed.renderContents().strip()
            d['weather'] = weather.replace('.Later','. Later').replace('&deg;F','F ')
            object_list.append(d)

        output = False 
        
        for each in object_list:
            if optteam in each['matchup']:
                output = "{0} at {1}({2})  Weather: {3}  Wind: {4}mph ({5}deg)".format(ircutils.underline(each['matchup']),\
                    each['park'], each['factor'], each['weather'], each['windspeed'], each['winddir'])
        
        if not output:
            irc.reply("No match-up found for: %s" % optteam)
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
