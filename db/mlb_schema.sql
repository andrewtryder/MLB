/* MLB TEAMS */
CREATE TABLE mlb (
    team TEXT PRIMARY KEY,
    eid INTEGER,
    roto TEXT,
    fulltrans TEXT,
    ename TEXT,
    short TEXT,
    yahoo TEXT,
    eshort TEXT,
    st TEXT,
    mlbc TEXT,
    cbs TEXT,
    playoffs TEXT
);
/* ONE ROW PER TEAM */
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('ARI','29','ARZ','Arizona Diamondbacks','Arizona','diamondbacks','ari','ari','arizona-diamondbacks','ari','ari','diamondbacks');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('ATL','15','ATL','Atlanta Braves','Atlanta','braves','atl','atl','atlanta-braves','atl','atl','braves');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('BAL','1','BAL','Baltimore Orioles','Baltimore','orioles','bal','bal','baltimore-orioles','bal','bal','orioles');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('BOS','2','BOS','Boston Red Sox','Boston','redsox','bos','bos','boston-red-sox','bos','bos','red sox');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('CHC','16','CHC','Chicago Cubs','Chicago Cubs','cubs','chc','chc','chicago-cubs','chc','chc','cubs');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('CIN','17','CIN','Cincinnati Reds','Cincinnati','reds','cin','cin','cincinnati-reds','cin','cin','reds');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('CLE','5','CLE','Cleveland Indians','Cleveland','indians','cle','cle','cleveland-indians','cle','cle','indians');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('COL','27','COL','Colorado Rockies','Colorado','rockies','col','col','colorado-rockies','col','col','rockies');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('CWS','4','CWS','Chicago White Sox','Chicago Sox','whitesox','chw','chw','chicago-white-sox','cws','chw','white sox');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('DET','6','DET','Detroit Tigers','Detroit','tigers','det','det','detroit-tigers','det','det','tigers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('HOU','18','HOU','Houston Astros','Houston','astros','hou','hou','houston-astros','hou','hou','astros');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('KC','7','KC','Kansas City Royals','Kansas City','royals','kan','kc','kansas-city-royals','kc','kc','royals');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('LAA','3','ANA','Los Angeles Angels','LA Angels','angels','laa','laa','los-angeles-angels','ana','laa','angels');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('LAD','19','LA','Los Angeles Dodgers','LA Dodgers','dodgers','lad','lad','los-angeles-dodgers','lad','lad','dodgers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('MIA','28','FLA','Miami Marlins','Miami','Miami','mia','mia','miami-marlins','mia','mia','marlins');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('MIL','8','MLW','Milwaukee Brewers','Milwaukee','brewers','mil','mil','milwaukee-brewers','mil','mil','brewers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('MIN','9','MIN','Minnesota Twins','Minnesota','twins','min','min','minnesota-twins','min','min','twins');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('NYM','21','NYM','New York Mets','NY Mets','mets','nym','nym','new-york-mets','nym','nym','mets');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('NYY','10','NYY','New York Yankees','NY Yankees','yankees','nyy','nyy','new-york-yankees','nyy','nyy','yankees');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('OAK','11','OAK','Oakland Athletics','Oakland','athletics','oak','oak','oakland-athletics','oak','oak','athletics');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('PHI','22','PHI','Philadelphia Phillies','Philadelphia','phillies','phi','phi','philadelphia-phillies','phi','phi','phillies');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('PIT','23','PIT','Pittsburgh Pirates','Pittsburgh','pirates','pit','pit','pittsburgh-pirates','pit','pit','pirates');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('SD','25','SD','San Diego Padres','San Diego','padres','sdg','sd','san-diego-padres','sd','sd','padres');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('SEA','12','SEA','Seattle Mariners','Seattle','mariners','sea','sea','seattle-mariners','sea','sea','mariners');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('SF','26','SF','San Francisco Giants','San Francisco','giants','sfo','sf','san-francisco-giants','sf','sf','giants');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('STL','24','STL','St. Louis Cardinals','St. Louis','cardinals','stl','stl','st.-louis-cardinals','stl','stl','cardinals');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('TB','30','TB','Tampa Bay Rays','Tampa Bay','rays','tam','tb','tampa-bay-rays','tb','tb','rays');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('TEX','13','TEX','Texas Rangers','Texas','rangers','tex','tex','texas-rangers','tex','tex','rangers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('TOR','14','TOR','Toronto Blue Jays','Toronto','bluejays','tor','tor','toronto-blue-jays','tor','tor','blue jays');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st,mlbc,cbs,playoffs) values ('WSH','20','WAS','Washington Nationals','Washington','nationals','was','wsh','washington-nationals','was','was','nationals');

/* MLB TEAM ALIASES */
CREATE TABLE mlbteamaliases (
    team TEXT,
    teamalias TEXT,
    FOREIGN KEY(team) REFERENCES mlb(team)
);
/* EACH ALIAS IS INDIVIDUAL LINE. SOME TEAMS WILL HAVE MORE THAN OTHERS. */
INSERT INTO mlbteamaliases (team, teamalias) values ('ARI','arizona');
INSERT INTO mlbteamaliases (team, teamalias) values ('ARI','diamondbacks');
INSERT INTO mlbteamaliases (team, teamalias) values ('ARI','arz');
INSERT INTO mlbteamaliases (team, teamalias) values ('ATL','braves');
INSERT INTO mlbteamaliases (team, teamalias) values ('ATL','atlanta');
INSERT INTO mlbteamaliases (team, teamalias) values ('BAL','baltimore');
INSERT INTO mlbteamaliases (team, teamalias) values ('BAL','orioles');
INSERT INTO mlbteamaliases (team, teamalias) values ('BOS','boston');
INSERT INTO mlbteamaliases (team, teamalias) values ('BOS','redsox');
INSERT INTO mlbteamaliases (team, teamalias) values ('BOS','bosox');
INSERT INTO mlbteamaliases (team, teamalias) values ('CHC','cubs');
INSERT INTO mlbteamaliases (team, teamalias) values ('CHC','chicubs');
INSERT INTO mlbteamaliases (team, teamalias) values ('CIN','cincinnati');
INSERT INTO mlbteamaliases (team, teamalias) values ('CIN','reds');
INSERT INTO mlbteamaliases (team, teamalias) values ('CLE','cleveland');
INSERT INTO mlbteamaliases (team, teamalias) values ('CLE','indians');
INSERT INTO mlbteamaliases (team, teamalias) values ('COL','colorado');
INSERT INTO mlbteamaliases (team, teamalias) values ('COL','rockies');
INSERT INTO mlbteamaliases (team, teamalias) values ('CWS','whitesox');
INSERT INTO mlbteamaliases (team, teamalias) values ('CWS','chw');
INSERT INTO mlbteamaliases (team, teamalias) values ('DET','tigers');
INSERT INTO mlbteamaliases (team, teamalias) values ('DET','detroit');
INSERT INTO mlbteamaliases (team, teamalias) values ('HOU','houston');
INSERT INTO mlbteamaliases (team, teamalias) values ('HOU','astros');
INSERT INTO mlbteamaliases (team, teamalias) values ('KC','KCR');
INSERT INTO mlbteamaliases (team, teamalias) values ('KC','kan');
INSERT INTO mlbteamaliases (team, teamalias) values ('KC','royals');
INSERT INTO mlbteamaliases (team, teamalias) values ('LAA','angels');
INSERT INTO mlbteamaliases (team, teamalias) values ('LAD','dodgers');
INSERT INTO mlbteamaliases (team, teamalias) values ('MIA','miami');
INSERT INTO mlbteamaliases (team, teamalias) values ('MIA','marlins');
INSERT INTO mlbteamaliases (team, teamalias) values ('MIL','brewers');
INSERT INTO mlbteamaliases (team, teamalias) values ('MIL','milwaukee');
INSERT INTO mlbteamaliases (team, teamalias) values ('MIN','minnesota');
INSERT INTO mlbteamaliases (team, teamalias) values ('MIN','twins');
INSERT INTO mlbteamaliases (team, teamalias) values ('NYM','mets');
INSERT INTO mlbteamaliases (team, teamalias) values ('NYY','yankees');
INSERT INTO mlbteamaliases (team, teamalias) values ('NYY','evilempire');
INSERT INTO mlbteamaliases (team, teamalias) values ('OAK','oakland');
INSERT INTO mlbteamaliases (team, teamalias) values ('OAK','athletics');
INSERT INTO mlbteamaliases (team, teamalias) values ('PHI','philadelphia');
INSERT INTO mlbteamaliases (team, teamalias) values ('PHI','phillies');
INSERT INTO mlbteamaliases (team, teamalias) values ('PIT','pittsburgh');
INSERT INTO mlbteamaliases (team, teamalias) values ('PIT','pirates');
INSERT INTO mlbteamaliases (team, teamalias) values ('SD','SDG');
INSERT INTO mlbteamaliases (team, teamalias) values ('SD','SDP');
INSERT INTO mlbteamaliases (team, teamalias) values ('SD','sandiego');
INSERT INTO mlbteamaliases (team, teamalias) values ('SD','padres');
INSERT INTO mlbteamaliases (team, teamalias) values ('SEA','seattle');
INSERT INTO mlbteamaliases (team, teamalias) values ('SEA','mariners');
INSERT INTO mlbteamaliases (team, teamalias) values ('SF','sfg');
INSERT INTO mlbteamaliases (team, teamalias) values ('SF','sfo');
INSERT INTO mlbteamaliases (team, teamalias) values ('SF','giants');
INSERT INTO mlbteamaliases (team, teamalias) values ('STL','stlouis');
INSERT INTO mlbteamaliases (team, teamalias) values ('STL','cardinals');
INSERT INTO mlbteamaliases (team, teamalias) values ('TB','tamponbay');
INSERT INTO mlbteamaliases (team, teamalias) values ('TB','tbr');
INSERT INTO mlbteamaliases (team, teamalias) values ('TB','rays');
INSERT INTO mlbteamaliases (team, teamalias) values ('TEX','texas');
INSERT INTO mlbteamaliases (team, teamalias) values ('TEX','rangers');
INSERT INTO mlbteamaliases (team, teamalias) values ('TOR','toronto');
INSERT INTO mlbteamaliases (team, teamalias) values ('TOR','bluejays');
INSERT INTO mlbteamaliases (team, teamalias) values ('TOR','jays');
INSERT INTO mlbteamaliases (team, teamalias) values ('WSH','was');
INSERT INTO mlbteamaliases (team, teamalias) values ('WSH','washington');
INSERT INTO mlbteamaliases (team, teamalias) values ('WSH','nationals');
INSERT INTO mlbteamaliases (team, teamalias) values ('WSH','nats');
INSERT INTO mlbteamaliases (team, teamalias) values ('WSH','expos');
