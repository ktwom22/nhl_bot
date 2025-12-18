import pandas as pd
import numpy as np
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# -----------------------------
# Load tonight's games CSV
# -----------------------------
df = pd.read_csv("nhl_tonight_model_ready.csv")

# -----------------------------
# Compute predictions
# -----------------------------
df['home_score'] = df['home_goal_diff_pg'] + df['home_implied_prob']
df['away_score'] = df['away_goal_diff_pg'] + df['away_implied_prob']
df['predicted_winner'] = np.where(df['home_score'] > df['away_score'],
                                  df['home_team'], df['away_team'])
df['predicted_spread'] = (df['home_goal_diff_pg'] - df['away_goal_diff_pg']).round(2)
df['predicted_total_goals'] = (df['home_GF_pg'] + df['away_GF_pg']).round(1)

# Build lookup dictionary
game_lookup = {}
for _, row in df.iterrows():
    game_lookup[row['home_team'].lower()] = row
    game_lookup[row['away_team'].lower()] = row

# -----------------------------
# Prediction function
# -----------------------------
def ask_game_prediction(team_name):
    key = team_name.lower()
    if key not in game_lookup:
        return f"No game found for {team_name}"
    row = game_lookup[key]
    return (
        f"{row['away_team']} at {row['home_team']}\n"
        f"Predicted winner: {row['predicted_winner']}\n"
        f"Predicted puckline (home - away): {row['predicted_spread']}\n"
        f"Predicted total goals (O/U): {row['predicted_total_goals']}"
    )

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__)

@app.route("/")
def index():
    return "NHL Prediction SMS Bot is running. Text a team name to the Twilio number."

@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip()

    resp = MessagingResponse()

    if not incoming_msg:
        resp.message("Please text a team name, e.g. Carolina Hurricanes")
        return str(resp)

    reply = ask_game_prediction(incoming_msg)
    resp.message(reply)

    return str(resp)


# -----------------------------
# Run app
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # Render.com prefers non-standard ports
