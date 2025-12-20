import pandas as pd
from datetime import datetime, timezone
import pytz
import os
import requests

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(DATA_DIR, "nhl_tonight_model_ready.csv")

# -----------------------------
# OddsAPI key (hardcoded)
# -----------------------------
ODDS_API_KEY = "671562f92f88a1a9638935021a068255"

# -----------------------------
# OddsAPI config
# -----------------------------
SPORT = "icehockey_nhl"
REGIONS = "us"
MARKETS = "h2h,spreads,totals"

# -----------------------------
# Local timezone (CHANGE IF NEEDED)
# -----------------------------
LOCAL_TZ = pytz.timezone("US/Eastern")

# -----------------------------
# Scraper
# -----------------------------
def scrape_games_today():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "dateFormat": "iso"
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("❌ OddsAPI error:", response.status_code, response.text)
        return []

    data = response.json()
    games = []

    today_local = datetime.now(LOCAL_TZ).date()

    print(f"📅 Local sports date: {today_local}")

    for game in data:
        try:
            # Parse UTC time from OddsAPI
            utc_time = datetime.strptime(
                game["commence_time"],
                "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            # Convert to local time
            local_time = utc_time.astimezone(LOCAL_TZ)

            # ✅ KEEP ALL GAMES PLAYED TODAY (LOCAL TIME)
            if local_time.date() != today_local:
                continue

            away = game["away_team"]
            home = game["home_team"]

            # Defaults (safe if odds missing)
            home_win_pct = 0.5
            away_win_pct = 0.5
            home_puckline = -1.5
            away_puckline = 1.5
            over_under = 5.5

            # Parse odds
            for bookmaker in game.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market.get("outcomes", []):
                            if o["name"] == home:
                                home_win_pct = 1 / abs(float(o["price"]))
                            elif o["name"] == away:
                                away_win_pct = 1 / abs(float(o["price"]))
                    elif market["key"] == "spreads":
                        for o in market.get("outcomes", []):
                            if o["name"] == home:
                                home_puckline = o.get("point", home_puckline)
                            elif o["name"] == away:
                                away_puckline = o.get("point", away_puckline)
                    elif market["key"] == "totals":
                        over_under = market.get("points", over_under)

            games.append({
                "game_date": local_time.strftime("%Y-%m-%d"),
                "start_time_local": local_time.strftime("%H:%M"),
                "away_team": away,
                "home_team": home,
                "home_win_pct": round(home_win_pct, 3),
                "away_win_pct": round(away_win_pct, 3),
                "goal_diff_matchup": 0,
                "home_Goals_For": 2.5,
                "away_Goals_For": 2.5,
                "home_puckline": home_puckline,
                "away_puckline": away_puckline,
                "over_under": over_under
            })

        except Exception as e:
            print("⚠️ Skipping game due to error:", e)

    return games

# -----------------------------
# Run scraper and save CSV
# -----------------------------
games = scrape_games_today()

if not games:
    print("❌ No games found for today")
else:
    df = pd.DataFrame(games)
    df = df.sort_values("start_time_local")

    df.to_csv(OUTPUT_CSV, index=False)

    print(f"✅ Saved {len(df)} games to:")
    print(OUTPUT_CSV)
    print(df[["away_team", "home_team", "start_time_local"]])
