from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os

app = Flask(__name__)

# -----------------------------
# Load tonight's games CSV
# -----------------------------
INPUT_CSV = "nhl_tonight_model_ready.csv"
OUTPUT_CSV = "nhl_tonight_picks.csv"

if not os.path.exists(INPUT_CSV):
    raise FileNotFoundError(f"{INPUT_CSV} not found. Please place the CSV in the project directory.")

df = pd.read_csv(INPUT_CSV)

# -----------------------------
# Helper functions
# -----------------------------
def normalize(text):
    return text.lower().strip()

def find_game(team_name):
    team_name = normalize(team_name)
    for _, row in df.iterrows():
        if team_name in normalize(row["away_team"]) or team_name in normalize(row["home_team"]):
            return row
    return None

def pro_decision(row):
    """Pro-style decision engine for ML, Spread, O/U picks."""
    # Moneyline pick
    ml_pick = row['home_team'] if row['home_win_pct'] >= row['away_win_pct'] else row['away_team']
    if abs(row['goal_diff_matchup']) > 2:
        ml_pick = row['home_team'] if row['goal_diff_matchup'] > 0 else row['away_team']

    # Spread pick (covers puckline)
    if ml_pick == row['home_team']:
        spread_pick = f"{row['home_team']} {row['home_puckline']:+}"
    else:
        spread_pick = f"{row['away_team']} {row['away_puckline']:+}"

    # O/U pick
    expected_total = row['home_Goals_For'] + row['away_Goals_For']
    ou_pick = "Over" if expected_total > row['over_under'] else "Under"

    return ml_pick, spread_pick, ou_pick

def save_pick(row, ml_pick, spread_pick, ou_pick):
    """Append pick to CSV for record-keeping."""
    data = {
        "away_team": row['away_team'],
        "home_team": row['home_team'],
        "ml_pick": ml_pick,
        "spread_pick": spread_pick,
        "ou_pick": ou_pick
    }
    if not os.path.exists(OUTPUT_CSV):
        pd.DataFrame([data]).to_csv(OUTPUT_CSV, index=False)
    else:
        pd.DataFrame([data]).to_csv(OUTPUT_CSV, mode='a', header=False, index=False)

# -----------------------------
# Flask routes
# -----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
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

    ml_pick, spread_pick, ou_pick = pro_decision(game)
    save_pick(game, ml_pick, spread_pick, ou_pick)

    response_text = (
        f"🏒 NHL PICK\n\n"
        f"{game['away_team']} @ {game['home_team']}\n\n"
        f"💰 Moneyline: {ml_pick}\n"
        f"📈 Spread: {spread_pick}\n"
        f"⚖️ O/U: {ou_pick}"
    )

    msg.body(response_text)
    return str(resp)

@app.route("/")
def home():
    return "NHL WhatsApp bot is live."

# -----------------------------
# Run Flask app
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
