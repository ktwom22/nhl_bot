from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os

app = Flask(__name__)

# -----------------------------
# Config
# -----------------------------
INPUT_CSV = "nhl_tonight_model_ready.csv"
OUTPUT_CSV = "nhl_tonight_picks.csv"

# Load CSV
if not os.path.exists(INPUT_CSV):
    raise FileNotFoundError(f"{INPUT_CSV} not found in project directory.")
df = pd.read_csv(INPUT_CSV)

# -----------------------------
# Helper functions
# -----------------------------
def normalize(text):
    return text.lower().strip()

def find_game(team_name):
    """
    Robust matching for incoming WhatsApp messages:
    - Full team name
    - Short names (first or last word)
    """
    team_name = normalize(team_name)
    for _, row in df.iterrows():
        away = normalize(row['away_team'])
        home = normalize(row['home_team'])

        # Full name match
        if team_name in away or team_name in home:
            return row
        # Last word match (e.g., Hurricanes -> Carolina Hurricanes)
        if team_name == away.split()[-1] or team_name == home.split()[-1]:
            return row
        # First word match (e.g., Carolina -> Carolina Hurricanes)
        if team_name == away.split()[0] or team_name == home.split()[0]:
            return row
    print(f"No match found for '{team_name}'")  # Debug
    return None

def pro_decision(row):
    """
    Pro-style ML, Spread, and O/U decision engine
    """
    # Moneyline pick
    ml_pick = row['home_team'] if row['home_win_pct'] >= row['away_win_pct'] else row['away_team']
    # Override if goal differential strongly favors one team
    if abs(row['goal_diff_matchup']) > 2:
        ml_pick = row['home_team'] if row['goal_diff_matchup'] > 0 else row['away_team']

    # Spread pick
    if ml_pick == row['home_team']:
        spread_pick = f"{row['home_team']} {row['home_puckline']:+}"
    else:
        spread_pick = f"{row['away_team']} {row['away_puckline']:+}"

    # Over/Under pick
    expected_total = row['home_Goals_For'] + row['away_Goals_For']
    ou_pick = "Over" if expected_total > row['over_under'] else "Under"

    return ml_pick, spread_pick, ou_pick

def save_pick(row, ml_pick, spread_pick, ou_pick):
    """Append today's pick to CSV for record keeping."""
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
    print(f"Incoming message: '{incoming}'")  # Debug log

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

    # Save to CSV
    save_pick(game, ml_pick, spread_pick, ou_pick)

    # Build response
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
