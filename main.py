from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd

app = Flask(__name__)

# Load tonight's games (already merged & cleaned)
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
    incoming = request.values.get("Body", "")
    resp = MessagingResponse()
    msg = resp.message()
    msg.body("WhatsApp bot is working!")
    return str(resp)


@app.route("/")
def home():
    return "NHL WhatsApp bot is live."



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
