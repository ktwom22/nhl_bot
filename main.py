from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd

app = Flask(__name__)

# Load tonight's games (must have columns for ML, puckline, O/U, and goal stats)
df = pd.read_csv("nhl_tonight_model_ready.csv")


def normalize(text):
    return text.lower().strip()


def find_game(team_name):
    team_name = normalize(team_name)
    for _, row in df.iterrows():
        if team_name in normalize(row["away_team"]) or team_name in normalize(row["home_team"]):
            return row
    return None


def pro_decision(row):
    # --- Moneyline ---
    ml_pick = row['home_team'] if row['home_win_pct'] >= row['away_win_pct'] else row['away_team']

    # If goal_diff_matchup strongly favors other team, override
    if abs(row['goal_diff_matchup']) > 2:
        ml_pick = row['home_team'] if row['goal_diff_matchup'] > 0 else row['away_team']

    # --- Spread ---
    # Determine which team is likely to cover
    if ml_pick == row['home_team']:
        spread_pick = f"{row['home_team']} {row['home_puckline']:+}"
    else:
        spread_pick = f"{row['away_team']} {row['away_puckline']:+}"

    # --- O/U ---
    expected_total = row['home_Goals_For'] + row['away_Goals_For']
    ou_pick = "Over" if expected_total > row['over_under'] else "Under"

    return ml_pick, spread_pick, ou_pick


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    # must return TwiML
    resp = MessagingResponse()
    msg = resp.message()
    msg.body("Test message")
    return str(resp)



@app.route("/")
def home():
    return "NHL WhatsApp bot is live."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
