from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os
import time
import shutil
from datetime import date

app = Flask(__name__)

# -----------------------------
# Config
# -----------------------------
SOURCE_CSV = "nhl_tonight_model_ready.csv"      # where your updater MAY be writing
INPUT_CSV = "/tmp/nhl_tonight_model_ready.csv"  # runtime copy (Render-safe)
OUTPUT_CSV = "/tmp/nhl_tonight_picks.csv"

df = pd.DataFrame()

# -----------------------------
# Helpers
# -----------------------------
def today_str():
    return date.today().strftime("%Y-%m-%d")

def normalize(text):
    return str(text).lower().strip()

# -----------------------------
# HARD SYNC + LOAD (NO FILTERING)
# -----------------------------
def load_data():
    global df

    print("\n===== DATA LOAD START =====")

    # Step 1: If source CSV exists, force-copy it into /tmp
    if os.path.exists(SOURCE_CSV):
        try:
            shutil.copyfile(SOURCE_CSV, INPUT_CSV)
            print("Copied source CSV → /tmp")
        except Exception as e:
            print("COPY ERROR:", e)

    # Step 2: Load from /tmp
    if not os.path.exists(INPUT_CSV):
        print("NO INPUT CSV FOUND ANYWHERE")
        df = pd.DataFrame()
        return

    try:
        print("CSV last modified:", time.ctime(os.path.getmtime(INPUT_CSV)))
        df = pd.read_csv(INPUT_CSV)
        print("Rows loaded:", len(df))
        print("Columns:", list(df.columns))

    except Exception as e:
        print("LOAD ERROR:", e)
        df = pd.DataFrame()

    print("===== DATA LOAD END =====\n")

# -----------------------------
# Game matching
# -----------------------------
def find_game(team_name):
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

# -----------------------------
# Picks
# -----------------------------
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

        expected_total = home_goals + away_goals
        ou_pick = "Over" if expected_total > over_under else "Under"

        return ml_pick, spread_pick, ou_pick

    except Exception as e:
        print("DECISION ERROR:", e)
        return "N/A", "N/A", "N/A"

# -----------------------------
# Save history
# -----------------------------
def save_pick(row, ml_pick, spread_pick, ou_pick):
    record = {
        "date": today_str(),
        "away_team": row.get("away_team", ""),
        "home_team": row.get("home_team", ""),
        "ml_pick": ml_pick,
        "spread_pick": spread_pick,
        "ou_pick": ou_pick
    }

    try:
        if os.path.exists(OUTPUT_CSV):
            hist = pd.read_csv(OUTPUT_CSV)

            duplicate = (
                (hist["date"] == record["date"]) &
                (hist["away_team"] == record["away_team"]) &
                (hist["home_team"] == record["home_team"])
            )

            if duplicate.any():
                print("Duplicate pick — skipped")
                return

            hist = pd.concat([hist, pd.DataFrame([record])])
            hist.to_csv(OUTPUT_CSV, index=False)
        else:
            pd.DataFrame([record]).to_csv(OUTPUT_CSV, index=False)

    except Exception as e:
        print("SAVE ERROR:", e)

# -----------------------------
# Routes
# -----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    load_data()  # FORCE HARD RELOAD

    incoming = request.values.get("Body", "").strip()
    print("Incoming:", incoming)

    resp = MessagingResponse()
    msg = resp.message()

    if df.empty:
        msg.body("No NHL games loaded yet.")
        return str(resp)

    game = find_game(incoming)
    if game is None:
        msg.body(
            "No game found.\n\n"
            "Try:\n• Bruins\n• Rangers\n• Maple Leafs"
        )
        return str(resp)

    ml_pick, spread_pick, ou_pick = pro_decision(game)
    save_pick(game, ml_pick, spread_pick, ou_pick)

    msg.body(
        f"🏒 NHL PICK\n\n"
        f"{game['away_team']} @ {game['home_team']}\n\n"
        f"💰 Moneyline: {ml_pick}\n"
        f"📈 Spread: {spread_pick}\n"
        f"⚖️ O/U: {ou_pick}"
    )

    return str(resp)

@app.route("/")
def home():
    return "NHL WhatsApp bot is live."

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
