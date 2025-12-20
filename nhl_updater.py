import os
import requests
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# -----------------------------
# Load environment
# -----------------------------
load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
if not ODDS_API_KEY:
    raise RuntimeError("❌ ODDS_API_KEY not found")

SPORT = "icehockey_nhl"

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(DATA_DIR, "nhl_tonight_model_ready.csv")

# -----------------------------
# Time handling (CRITICAL FIX)
# -----------------------------
LOCAL_TZ = ZoneInfo("America/New_York")  # NHL standard
today_local = datetime.now(LOCAL_TZ).date()

print(f"📅 NHL Day (ET): {today_local}")

# -----------------------------
# OddsAPI request
# -----------------------------
URL = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"

params = {
    "apiKey": ODDS_API_KEY,
    "regions": "us",
    "markets": "h2h,spreads,totals",
    "oddsFormat": "american",
    "dateFormat": "iso"
}

print("📡 Fetching NHL games from OddsAPI...")
response = requests.get(URL, params=params)

if response.status_code != 200:
    raise RuntimeError(f"OddsAPI error: {response.text}")

games = response.json()
rows = []

# -----------------------------
# Parse games
# -----------------------------
for game in games:
    try:
        commence_utc = datetime.strptime(
            game["commence_time"],
            "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)

        commence_local = commence_utc.astimezone(LOCAL_TZ)

        # FILTER BY LOCAL NHL DAY (FIXED)
        if commence_local.date() != today_local:
            continue

        home = game["home_team"]
        away = game["away_team"]

        home_spread = -1.5
        away_spread = 1.5
        total = 6

        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] == "spreads":
                    for o in market["outcomes"]:
                        if o["name"] == home:
                            home_spread = o["point"]
                        elif o["name"] == away:
                            away_spread = o["point"]

                elif market["key"] == "totals":
                    total = market["outcomes"][0]["point"]

        rows.append({
            "game_date": str(today_local),
            "away_team": away,
            "home_team": home,
            "home_win_pct": 0.5,
            "away_win_pct": 0.5,
            "goal_diff_matchup": 0,
            "home_Goals_For": 3.1,
            "away_Goals_For": 3.0,
            "home_puckline": home_spread,
            "away_puckline": away_spread,
            "over_under": total,
            "start_time_et": commence_local.strftime("%H:%M")
        })

        print(f"✅ Added: {away} @ {home} ({commence_local.strftime('%I:%M %p ET')})")

    except Exception as e:
        print("⚠️ Skipping game:", e)

# -----------------------------
# Save CSV
# -----------------------------
df = pd.DataFrame(rows)

if df.empty:
    print("❌ No games found for today")
else:
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"💾 Saved {len(df)} games → {OUTPUT_CSV}")
