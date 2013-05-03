/* MLB TEAMS */
CREATE TABLE mlb (team text primary key, eid integer, roto text, fulltrans text, ename text, short text, yahoo text, eshort text, st text);
/* ONE PER TEAM */
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('ARI','29','ARZ','Arizona Diamondbacks','Arizona','diamondbacks','ari','ari','arizona-diamondbacks');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('ATL','15','ATL','Atlanta Braves','Atlanta','braves','atl','atl','atlanta-braves');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('BAL','1','BAL','Baltimore Orioles','Baltimore','orioles','bal','bal','baltimore-orioles');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('BOS','2','BOS','Boston Red Sox','Boston','redsox','bos','bos','boston-red-sox');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('CHC','16','CHC','Chicago Cubs','Chicago Cubs','cubs','chc','chc','chicago-cubs');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('CIN','17','CIN','Cincinnati Reds','Cincinnati','reds','cin','cin','chicago-white-sox');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('CLE','5','CLE','Cleveland Indians','Cleveland','indians','cle','cle','cleveland-indians');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('COL','27','COL','Colorado Rockies','Colorado','rockies','col','col','colorado-rockies');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('CWS','4','CWS','Chicago White Sox','Chicago Sox','whitesox','chw','chw','chicago-white-sox');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('DET','6','DET','Detroit Tigers','Detroit','tigers','det','det','detroit-tigers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('HOU','18','HOU','Houston Astros','Houston','astros','hou','hou','houston-astros');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('KC','7','KC','Kansas City Royals','Kansas City','royals','kan','kc','kansas-city-royals');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('LAA','3','ANA','Los Angeles Angels','LA Angels','angels','laa','laa','los-angeles-angels');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('LAD','19','LA','Los Angeles Dodgers','LA Dodgers','dodgers','lad','lad','los-angeles-dodgers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('MIA','28','FLA','Miami Marlins','Miami','Miami','mia','mia','miami-marlins');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('MIL','8','MLW','Milwaukee Brewers','Milwaukee','brewers','mil','mil','milwaukee-brewers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('MIN','9','MIN','Minnesota Twins','Minnesota','twins','min','min','minnesota-twins');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('NYM','21','NYM','New York Mets','NY Mets','mets','nym','nym','new-york-mets');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('NYY','10','NYY','New York Yankees','NY Yankees','yankees','nyy','nyy','new-york-yankees');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('OAK','11','OAK','Oakland Athletics','Oakland','athletics','oak','oak','oakland-athletics');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('PHI','22','PHI','Philadelphia Phillies','Philadelphia','phillies','phi','phi','philadelphia-phillies');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('PIT','23','PIT','Pittsburgh Pirates','Pittsburgh','pirates','pit','pit','pittsburgh-pirates');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('SD','25','SD','San Diego Padres','San Diego','padres','sdg','sd','san-diego-padres');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('SEA','12','SEA','Seattle Mariners','Seattle','mariners','sea','sea','seattle-mariners');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('SF','26','SF','San Francisco Giants','San Francisco','giants','sfo','sf','san-francisco-giants');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('STL','24','STL','St. Louis Cardinals','St. Louis','cardinals','stl','stl','st.-louis-cardinals');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('TB','30','TB','Tampa Bay Rays','Tampa Bay','rays','tam','tb','tampa-bay-rays');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('TEX','13','TEX','Texas Rangers','Texas','rangers','tex','tex','texas-rangers');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('TOR','14','TOR','Toronto Blue Jays','Toronto','bluejays','tor','tor','toronto-blue-jays');
INSERT INTO mlb (team,eid,roto,fulltrans,ename,short,yahoo,eshort,st) values ('WSH','20','WAS','Washington Nationals','Washington','nationals','was','wsh','washington-nationals');

/* MLB TEAM ALIASES */
CREATE TABLE mlbteamaliases (
    team TEXT,
    teamalias TEXT,
    FOREIGN KEY(team) REFERENCES mlb(team)
);
/* EACH ALIAS IS INDIVIDUAL LINE. SOME TEAMS WILL HAVE MORE THAN OTHERS. */
INSERT INTO mlbteamaliases (team, teamalias) values ('ARI','diamondbacks');
INSERT INTO mlbteamaliases (team, teamalias) values ('DET','tigers');
