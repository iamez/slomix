# Website Review Notes
> Date: 2024-12-28
> Reviewer: [You]

## How to Use This
Open the website (`http://localhost:8000` or your server URL) and browse each section.
Add your notes under each category as you explore.

---

## What I Like (Keep These)
<!-- Things working well, good design choices, features that feel polished -->
i like the search box
then the live online button, notification bell, user logged in and logout function
then we has an icon of LS(what is that) and next oto it says Slomix.gg, slomix should be lowercases 
buttons home , sessions, leaderboards, maps, weapons, profile are fine but the function of each button is only "half" working for exmaple;
when i click maps button it only shows a page with title maps but no content inside it, the content for maps should be added... which maps wer played historically? how many times has supply ben played, or other map? note that we are on stopwatch so each map has round 1 and round 2, so one map of supply is played twice.. if thers 4 rounds of supply its ben played 2 times... for more information look at the docs in parrent directory ../docs and look how last_session works to get more info about maps played

when i click weapons button it only shows a page with title weapons but no content inside it, this is similar to maps button, the content for weapons should be added... which weapons were used historically? how many times has each weapon been used? what is the accuracy of each weapon? headshot percentage? etc... for more information look at the docs in parrent directory ../docs and look how last_session weapon (im not sure this is the command but we have comprehensive weapon stats for each player) works to get more info about weapons used then we can sort it by popularity, avg accuracy, etc 

when i click on profile button it shows a page with title profile but the content seems hardcoded, the content for profile should be added... what is the total kills, deaths, kd ratio, win rate, total matches played, total time played, favorite weapon, favorite map, most used 3 other alieses, is player linked to discord username or not, favorite map/most played map/ highest dpm recorded, lowest dpm recorded, last seen... etc... for more information look at the docs in parrent directory ../docs and look how player stats works to get more info about player profile and what else can be added

when i click on leaderboard no stats appear untill i click on one of the fucntions for example; 
- clicking on kd ratio shows the leaderboard sorted by kd ratio and so on.... by deafult when opening leaderboard we should default to season, and sort by most games played, so we dont confuse the user with empty leaderboard.. it works well the leaderboard just on first click its empty untill user clicks a deserided category to sort by

when i click on sessions, it works well but if that session has data/stats going after midnight the it will create two sessions for the same date, but sort the ones before and after midnight in its own session, stats i belive in db are still linked to the same session id but on frontend we should merge those two sessions into one session if they share the same date even if they go past midnight, so user dont get confused seeing two sessions for the same date 

---

## Bugs / Issues to Fix

1. **Logo text**: "Slomix" should be lowercase "slomix" (line 189 in index.html)
2. **Leaderboard empty on load**: No data until user clicks a filter - should default to season + games
3. **Sessions midnight split**: Sessions spanning midnight show as 2 entries (group by gaming_session_id)
4. **Broken HTML**: Extra closing `</div>` tags at lines 575-576 in index.html
5. **Charts placeholder data**: ELO chart shows hardcoded data, not real player history
6. **CMD+K not wired**: Search shortcut shown but doesn't work

---

## Missing / Incomplete Features

### Maps Page (API needs expansion)
- API `/api/stats/maps` only returns map names - need full stats
- Times played per map (remember: 2 rounds = 1 match in stopwatch)
- Win rate per team per map
- Average duration per map

### Weapons Page (API READY - just wire frontend!)
- API `/api/stats/weapons` returns real kill counts - USE IT
- Need: sorting by popularity, accuracy, headshot %
- Need: weapon categories (Rifles, SMGs, Heavy, etc.)

### Profile Page (API READY - wire more fields!)
- API `/api/stats/player/{name}` has: kills, deaths, K/D, DPM, wins, losses, win_rate, playtime, XP
- Missing in frontend: favorite weapon, favorite map, highest/lowest DPM, aliases, discord link status

---

## New Features to Add
<!-- Ideas for new functionality -->

-

---

## UI/UX Improvements
<!-- Layout, design, usability suggestions -->

-

---

## Wild Ideas / Experiments
<!-- Ambitious features, innovative concepts to try -->

-

---

## Page-by-Page Notes

### Home Page
- Hero section:
- Search bar:
- Live status widgets:
- Stats widgets:

### Sessions Page
- Session list:
- Session details:

### Leaderboards Page
- Filters:
- Table display:

### Maps Page
- Current state:
- What it should show:

### Weapons Page
- Current state:
- What it should show:

### Profile Page
- Stats display:
- Achievements:
- Charts:
- Recent matches:

### Modals
- Match Details:
- Player Comparison:

---

## Priority List (After Review)

### COMPLETED (Dec 28, 2024)
1. [x] Fix leaderboard default to season + games - now loads with data on first visit
2. [x] Fix logo text casing - "slomix.gg" now lowercase
3. [x] Fix broken HTML closing tags - removed extra </div> tags
4. [x] Wire Weapons page to API - now loads real weapon kill stats
5. [x] Wire Profile page to full API data - added favorite weapon/map, DPM records, aliases, discord status
6. [x] Expand Maps API with full statistics - returns matches, win rates, avg DPM, duration
7. [x] Build Maps page frontend - beautiful cards with all stats
8. [x] Fix Sessions midnight grouping - now groups by gaming_session_id

### Still TODO
- Add real chart data to profile performance graph (currently placeholder)

---

## API Endpoints Ready to Use

```
GET /api/stats/overview        - Homepage stats (working)
GET /api/stats/weapons         - Weapon kills by type (READY - not used!)
GET /api/stats/player/{name}   - Full player stats (READY - partially used)
GET /api/stats/leaderboard     - Leaderboard (working)
GET /api/stats/records         - All-time records (READY - no page!)
GET /api/sessions              - Session list (working)
GET /api/sessions/{date}       - Session details (working)
GET /api/player/{name}/matches - Player match history (READY)
GET /api/stats/compare         - Player comparison (READY)
```

## Database Fields Available

Per player per round: kills, deaths, headshots, damage_given, damage_received,
shots, hits, accuracy, revives, gibs, xp, time_played_seconds,
knife_kills, luger_kills, mp40_kills, thompson_kills, fg42_kills, panzerfaust_kills, etc.

