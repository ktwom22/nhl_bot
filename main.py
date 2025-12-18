from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd

app = Flask(__name__)

# Load tonight's games
df = pd.read_csv("nhl_tonight_model_ready.csv")

def normalize(text):
    return text.lower().strip()

def find_game(team_name):
    team_name = normalize(team_name)
    for _, row in df.iterrows():
        if team_name in normalize(row["away_team"]) or team_name in normalize(row["home_team"]):
            return row
    return None

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
            "• Hurricanes\n"
            "• Bruins\n"
            "• Maple Leafs"
        )
        return str(resp)

    # Determine Moneyline pick
    ml_pick = game["home_team"] if game["home_moneyline"] > game["away_moneyline"] else game["away_team"]

    response_text = (
        f"🏒 NHL PICK\n\n"
        f"{game['away_team']} @ {game['home_team']}\n\n"
        f"💰 Moneyline: {ml_pick}\n"
        f"📈 Spread: {game['home_team']} {game['home_puckline']} / "
        f"{game['away_team']} {game['away_puckline']}\n"
        f"⚖️ O/U: {game['over_under']}"
    )

    msg.body(response_text)
    return str(resp)

@app.route("/")
def home():
    return "NHL WhatsApp bot is live."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
