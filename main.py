from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta, timezone, date
import os
from dotenv import load_dotenv


# =========================
# CONFIG
# =========================
AFC_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTvmRRSRI6w9jf34bTSkJZJKRYETRyxanPOKhsvfuOUQUt67OfzcyFycB1eBOp-THmtBpoCnfN5CM-d/pub?gid=0&single=true&output=csv"
NFC_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTvmRRSRI6w9jf34bTSkJZJKRYETRyxanPOKhsvfuOUQUt67OfzcyFycB1eBOp-THmtBpoCnfN5CM-d/pub?gid=1030664158&single=true&output=csv"

load_dotenv()
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
if not ODDS_API_KEY:
    raise RuntimeError("❌ ODDS_API_KEY not found")

SPORT = "americanfootball_nfl"
REGIONS = "us"
MARKETS = "spreads,totals"

HOME_FIELD_ADV = 1.5
LEAGUE_AVG_TOTAL = 44

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURRENT_WEEK_FILE = os.path.join(BASE_DIR, "nfl_this_week_picks.csv")
ARCHIVE_FILE = os.path.join(BASE_DIR, "nfl_picks_archive.csv")

TEAM_NAME_MAP = {
    "LA Chargers": "Los Angeles Chargers",
    "LA Rams": "Los Angeles Rams",
    "NY Giants": "New York Giants",
    "NY Jets": "New York Jets"
}

# =========================
# TIME FILTER (UPCOMING GAMES THROUGH TUESDAY 05:00 UTC)
# =========================
def is_upcoming_slate(game_time_utc):
    kickoff = datetime.fromisoformat(game_time_utc.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    days_to_tuesday = (1 - weekday) % 7
    tuesday_morning = (now + timedelta(days=days_to_tuesday)).replace(
        hour=5, minute=0, second=0, microsecond=0
    )
    if tuesday_morning <= now:
        tuesday_morning += timedelta(days=7)
    return now <= kickoff <= tuesday_morning

# =========================
# HELPERS
# =========================
def clean_team(name):
    return name.replace("*", "").replace("+", "").strip()

def load_team_stats():
    afc = pd.read_csv(AFC_URL)
    nfc = pd.read_csv(NFC_URL)
    df = pd.concat([afc, nfc], ignore_index=True)
    df["team"] = df["Tm"].apply(clean_team)
    df["games"] = df["W"] + df["L"] + df["T"]
    df["PF_pg"] = df["PF"] / df["games"]
    df["PA_pg"] = df["PA"] / df["games"]
    df["PD_pg"] = df["PF_pg"] - df["PA_pg"]
    return df[["team", "PF_pg", "PA_pg", "PD_pg", "MoV", "SoS", "SRS", "OSRS", "DSRS"]]

def get_odds():
    r = requests.get(
        f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds",
        params={
            "apiKey": ODDS_API_KEY,
            "regions": REGIONS,
            "markets": MARKETS,
            "oddsFormat": "decimal"
        }
    )
    r.raise_for_status()
    return r.json()

def project_scores(home_stats, away_stats):
    raw_total = (home_stats.PF_pg + away_stats.PF_pg + home_stats.PA_pg + away_stats.PA_pg)/2
    sos_adj = (home_stats.SoS + away_stats.SoS)/2
    mov_adj = (home_stats.MoV + away_stats.MoV)*0.3
    projected_total = np.clip(raw_total + sos_adj + mov_adj, 35, 55)
    neutral_margin = home_stats.SRS - away_stats.SRS
    margin = neutral_margin + HOME_FIELD_ADV
    margin_share = 0.5 + (margin / LEAGUE_AVG_TOTAL)
    home_attack = home_stats.OSRS - away_stats.DSRS
    away_attack = away_stats.OSRS - home_stats.DSRS
    hw = math.exp(home_attack)
    aw = math.exp(away_attack)
    attack_share = hw / (hw + aw)
    home_share = np.clip(0.6*margin_share + 0.4*attack_share, 0.35, 0.65)
    home_pts = round(projected_total*home_share, 1)
    away_pts = round(projected_total - home_pts, 1)
    return home_pts, away_pts

def make_pick(df, game):
    if not is_upcoming_slate(game["commence_time"]):
        return None
    home = TEAM_NAME_MAP.get(game["home_team"], game["home_team"])
    away = TEAM_NAME_MAP.get(game["away_team"], game["away_team"])
    home_stats = df[df.team == home]
    away_stats = df[df.team == away]
    if home_stats.empty or away_stats.empty:
        return None
    home_stats = home_stats.iloc[0]
    away_stats = away_stats.iloc[0]
    home_pts, away_pts = project_scores(home_stats, away_stats)
    home_spread = away_spread = total_line = None
    for market in game["bookmakers"][0]["markets"]:
        if market["key"] == "spreads":
            for o in market["outcomes"]:
                if o["name"] == home: home_spread = o["point"]
                elif o["name"] == away: away_spread = o["point"]
        if market["key"] == "totals":
            total_line = market["outcomes"][0]["point"]
    if home_spread is None or away_spread is None:
        return None
    spread_pick = home if home_pts+home_spread>away_pts else away if away_pts+away_spread>home_pts else "PUSH"
    ou_pick = "OVER" if (home_pts+away_pts)>total_line else "UNDER"
    return {
        "game": f"{away} @ {home}",
        "home_spread": home_spread,
        "away_spread": away_spread,
        "spread_pick": spread_pick,
        "total_line": total_line,
        "ou_pick": ou_pick,
        "projected_home_points": home_pts,
        "projected_away_points": away_pts,
        "projected_total": round(home_pts+away_pts, 1)
    }

# =========================
# RUN & ARCHIVE
# =========================
def run():
    df = load_team_stats()
    odds = get_odds()
    picks = []
    for game in odds:
        pick = make_pick(df, game)
        if pick: picks.append(pick)
    current_week_df = pd.DataFrame(picks)
    current_week_df.to_csv(CURRENT_WEEK_FILE, index=False)
    if os.path.exists(ARCHIVE_FILE):
        archive_df = pd.read_csv(ARCHIVE_FILE)
    else:
        archive_df = pd.DataFrame(columns=current_week_df.columns)
    combined_df = pd.concat([archive_df, current_week_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset="game", keep="last")
    combined_df.to_csv(ARCHIVE_FILE, index=False)
    return current_week_df

# =========================
# FLASK BOT
# =========================
app = Flask(__name__)

def today():
    return date.today().strftime("%Y-%m-%d")

def load_current_week():
    if os.path.exists(CURRENT_WEEK_FILE):
        df = pd.read_csv(CURRENT_WEEK_FILE)
        return df
    return pd.DataFrame()

def normalize(x):
    return str(x).lower().strip()

def find_pick(df, team):
    team = normalize(team)
    for _, r in df.iterrows():
        if team in normalize(r["game"]):
            return r
    return None

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "")
    df = load_current_week()
    resp = MessagingResponse()
    msg = resp.message()
    if df.empty:
        msg.body("No NFL picks available for this week yet.")
        return str(resp)
    pick = find_pick(df, incoming)
    if pick is None:
        msg.body("Team not found. Try Patriots, Chiefs, Packers, etc.")
        return str(resp)
    msg.body(
        f"🏈 NFL PICK ({today()})\n\n"
        f"{pick['game']}\n"
        f"💰 ML Spread: {pick['spread_pick']}\n"
        f"⚖️ O/U: {pick['ou_pick']}\n"
        f"📊 Projected Home: {pick['projected_home_points']}, Away: {pick['projected_away_points']}\n"
        f"📈 Total Projected: {pick['projected_total']}"
    )
    return str(resp)

@app.route("/")
def home():
    return "NFL WhatsApp bot live."

@app.route("/archive")
def archive():
    if os.path.exists(ARCHIVE_FILE):
        df = pd.read_csv(ARCHIVE_FILE)
        return df.tail(50).to_html()
    return "No historical picks yet."

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    results = run()
    print(results)
    app.run(host="0.0.0.0", port=10000)
