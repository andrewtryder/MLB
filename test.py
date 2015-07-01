###
# see LICENSE.txt for information.
###

from supybot.test import *

class MLBTestCase(PluginTestCase):
    plugins = ('MLB',)
    
    def testMLB(self):
        # milbplayerinfo, milbplayerseason, mlballstargame, mlbarrests, mlbawards,
        # mlbbox, mlbcareerleaders, mlbcareerstats, mlbchanlineup, mlbcountdown, mlbcyyoung,
        # mlbdailyleaders, mlbejections, mlbgamesbypos, mlbgamestats, mlbgameumps,
        # mlbhittingstreaks, mlbinjury, mlbleaders, mlblineup, mlbmanager, mlbpayroll, mlbpitcher,
        # mlbplayercontract, mlbplayerinfo, mlbplayernews, mlbplayoffs, mlbpowerrankings, mlbprob,
        # mlbremaining, mlbroster, mlbrosterstats, mlbschedule, mlbseasonstats, mlbseries,
        # mlbstandings, mlbteamleaders, mlbteams, mlbteamtrans, mlbtrans, mlbvaluations,
        # mlbweather, and mlbworldseries
        self.assertNotError('milbplayerinfo Mike Trout')
        self.assertNotError('milbplayerseason 2010 mike trout')
        self.assertNotError('mlballstargame 2013')
        self.assertNotError('mlbarrests')
        self.assertNotError('mlbawards 2013')
        self.assertNotError('mlbcareerleaders batting batavg')
