from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os

app = Flask(__name__)

# -----------------------------
# Config
# -----------------------------
INPUT_CSV = "nhl_tonight_model_ready.csv"
# Use /tmp for Render deployments (writable folder)
OUTPUT_CSV = "/tmp/nhl_tonight_picks.csv"

# -----------------------------
# Load CSV safely
# -----------------------------
try:
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} games from {INPUT_CSV}")
except Exception as e:
    print(f"Error loading input CSV: {e}")
    df = pd.DataFrame()  # empty DataFrame to prevent crash

# -----------------------------
# Helper functions
# -----------------------------
def normalize(text):
    return text.lower().strip()

def find_game(team_name):
    """Robust matching: full name, first word, or last word"""
    team_name = normalize(team_name)
    for _, row in df.iterrows():
        away = normalize(row.get('away_team', ''))
        home = normalize(row.get('home_team', ''))

        if team_name in away or team_name in home:
            return row
        if team_name == away.split()[-1] or team_name == home.split()[-1]:
            return row
        if team_name == away.split()[0] or team_name == home.split()[0]:
            return row
    print(f"No match found for '{team_name}'")  # debug
    return None

def pro_decision(row):
    """Safe decision engine for ML, Spread, O/U"""
    try:
        home_win_pct = float(row.get('home_win_pct', 0))
        away_win_pct = float(row.get('away_win_pct', 0))
        goal_diff = float(row.get('goal_diff_matchup', 0))
        home_goals = float(row.get('home_Goals_For', 0))
        away_goals = float(row.get('away_Goals_For', 0))
        home_puckline = float(row.get('home_puckline', 0))
        away_puckline = float(row.get('away_puckline', 0))
        over_under = float(row.get('over_under', 6))

        # Moneyline
        ml_pick = row['home_team'] if home_win_pct >= away_win_pct else row['away_team']
        if abs(goal_diff) > 2:
            ml_pick = row['home_team'] if goal_diff > 0 else row['away_team']

        # Spread
        spread_pick = f"{row['home_team']} {home_puckline:+}" if ml_pick == row['home_team'] else f"{row['away_team']} {away_puckline:+}"

        # O/U
        expected_total = home_goals + away_goals
        ou_pick = "Over" if expected_total > over_under else "Under"

        print(f"Picks: ML={ml_pick}, Spread={spread_pick}, O/U={ou_pick}")
        return ml_pick, spread_pick, ou_pick
    except Exception as e:
        print(f"Error in decision engine: {e}")
        return "N/A", "N/A", "N/A"

def save_pick(row, ml_pick, spread_pick, ou_pick):
    """Append pick to CSV safely"""
    data = {
        "away_team": row.get('away_team', ''),
        "home_team": row.get('home_team', ''),
        "ml_pick": ml_pick,
        "spread_pick": spread_pick,
        "ou_pick": ou_pick
    }
    try:
        if not os.path.exists(OUTPUT_CSV):
            pd.DataFrame([data]).to_csv(OUTPUT_CSV, index=False)
        else:
            pd.DataFrame([data]).to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
    except Exception as e:
        print(f"Error saving picks to CSV: {e}")

# -----------------------------
# Flask routes
# -----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    print(f"Incoming message: '{incoming}'")  # debug

    resp = MessagingResponse()
    msg = resp.message()

    game = find_game(incoming)
    if game is None:
        msg.body(
            "No game found for that team tonight.\n"
            "Try texting a team name like:\n"
            "• Hurricanes\n• Bruins\n• Maple Leafs"
        )
        return str(resp)

    # Make picks
    ml_pick, spread_pick, ou_pick = pro_decision(game)

    # Save picks
    save_pick(game, ml_pick, spread_pick, ou_pick)

    # Respond
    if ml_pick == "N/A":
        msg.body("Stats incomplete for this game. Cannot provide a pick.")
    else:
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
# Run Flask app
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
