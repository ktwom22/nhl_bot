from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os
from datetime import date

app = Flask(__name__)

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

INPUT_CSV = os.path.join(DATA_DIR, "nhl_tonight_model_ready.csv")
CURRENT_PICKS_CSV = os.path.join(DATA_DIR, "nhl_tonight_picks.csv")
ARCHIVE_PICKS_CSV = os.path.join(DATA_DIR, "nhl_picks_archive.csv")

# -----------------------------
# Helpers
# -----------------------------
def today_str():
    return date.today().strftime("%Y-%m-%d")

def debug(msg):
    print("DEBUG:", msg)

def load_games():
    if not os.path.exists(INPUT_CSV):
        debug("No games CSV found")
        return pd.DataFrame()
    df = pd.read_csv(INPUT_CSV)
    debug(f"CSV loaded: {len(df)} rows")
    if "game_date" not in df.columns:
        df["game_date"] = today_str()
    df["game_date"] = pd.to_datetime(df["game_date"], errors='coerce').dt.date.astype(str)
    df = df[df["game_date"] == today_str()]
    debug(f"Filtered today: {len(df)} rows")
    return df

def normalize(text):
    return str(text).lower().strip()

def find_game(df, team_name):
    team_name = normalize(team_name)
    for _, row in df.iterrows():
        away = normalize(row.get("away_team", ""))
        home = normalize(row.get("home_team", ""))
        if team_name in away or team_name in home:
            return row
        if team_name == away.split()[-1] or team_name == home.split()[-1]:
            return row
        if team_name == away.split()[0] or team_name == home.split()[0]:
            return row
    return None

def pro_decision(row):
    try:
        home_win_pct = float(row.get("home_win_pct", 0))
        away_win_pct = float(row.get("away_win_pct", 0))
        goal_diff = float(row.get("goal_diff_matchup", 0))
        home_goals = float(row.get("home_Goals_For", 0))
        away_goals = float(row.get("away_Goals_For", 0))
        home_puckline = float(row.get("home_puckline", -1.5))
        away_puckline = float(row.get("away_puckline", 1.5))
        over_under = float(row.get("over_under", 6))

        ml_pick = row["home_team"] if home_win_pct >= away_win_pct else row["away_team"]
        if abs(goal_diff) > 2:
            ml_pick = row["home_team"] if goal_diff > 0 else row["away_team"]

        spread_pick = (
            f"{row['home_team']} {home_puckline:+}"
            if ml_pick == row["home_team"]
            else f"{row['away_team']} {away_puckline:+}"
        )

        ou_pick = "Over" if (home_goals + away_goals) > over_under else "Under"

        return ml_pick, spread_pick, ou_pick
    except Exception as e:
        debug("Decision error: " + str(e))
        return "N/A", "N/A", "N/A"

def save_pick(row, ml, spread, ou):
    record = {
        "date": today_str(),
        "away_team": row.get("away_team", ""),
        "home_team": row.get("home_team", ""),
        "ml_pick": ml,
        "spread_pick": spread,
        "ou_pick": ou
    }

    # Current picks
    if os.path.exists(CURRENT_PICKS_CSV):
        df_current = pd.read_csv(CURRENT_PICKS_CSV)
        duplicate = ((df_current["date"] == record["date"]) &
                     (df_current["away_team"] == record["away_team"]) &
                     (df_current["home_team"] == record["home_team"]))
        if not duplicate.any():
            df_current = pd.concat([df_current, pd.DataFrame([record])])
            df_current.to_csv(CURRENT_PICKS_CSV, index=False)
            debug("Pick added to current picks")
        else:
            debug("Duplicate pick, skipped current picks")
    else:
        pd.DataFrame([record]).to_csv(CURRENT_PICKS_CSV, index=False)
        debug("Current picks CSV created")

    # Archive picks
    if os.path.exists(ARCHIVE_PICKS_CSV):
        df_archive = pd.read_csv(ARCHIVE_PICKS_CSV)
        df_archive = pd.concat([df_archive, pd.DataFrame([record])])
        df_archive.to_csv(ARCHIVE_PICKS_CSV, index=False)
        debug("Pick added to archive")
    else:
        pd.DataFrame([record]).to_csv(ARCHIVE_PICKS_CSV, index=False)
        debug("Archive CSV created")

# -----------------------------
# Flask routes
# -----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    df_games = load_games()
    incoming = request.values.get("Body", "").strip()
    debug("Incoming message: " + incoming)

    resp = MessagingResponse()
    msg = resp.message()

    if df_games.empty:
        msg.body("No NHL games loaded for today yet.")
        return str(resp)

    game = find_game(df_games, incoming)
    if game is None:
        msg.body(
            "No game found for that team tonight.\nTry:\n• Bruins\n• Rangers\n• Maple Leafs"
        )
        return str(resp)

    ml, spread, ou = pro_decision(game)
    save_pick(game, ml, spread, ou)

    msg.body(
        f"🏒 NHL PICK ({today_str()})\n\n"
        f"{game['away_team']} @ {game['home_team']}\n\n"
        f"💰 Moneyline: {ml}\n"
        f"📈 Spread: {spread}\n"
        f"⚖️ O/U: {ou}"
    )
    return str(resp)

@app.route("/")
def home():
    return "NHL WhatsApp bot is live."

@app.route("/archive")
def archive():
    if os.path.exists(ARCHIVE_PICKS_CSV):
        return pd.read_csv(ARCHIVE_PICKS_CSV).tail(50).to_html()
    return "No historical picks yet."

# -----------------------------
# Run Flask
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
