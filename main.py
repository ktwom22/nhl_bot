from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os
from datetime import date

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

INPUT_CSV = os.path.join(DATA_DIR, "nhl_tonight_model_ready.csv")
CURRENT_PICKS = os.path.join(DATA_DIR, "nhl_tonight_picks.csv")
ARCHIVE = os.path.join(DATA_DIR, "nhl_picks_archive.csv")

def today():
    return date.today().strftime("%Y-%m-%d")

def load_games():
    if not os.path.exists(INPUT_CSV):
        return pd.DataFrame()
    df = pd.read_csv(INPUT_CSV)
    return df[df["game_date"] == today()]

def normalize(x):
    return str(x).lower().strip()

def find_game(df, team):
    team = normalize(team)
    for _, r in df.iterrows():
        if team in normalize(r["home_team"]) or team in normalize(r["away_team"]):
            return r
    return None

def decide(row):
    ml = row["home_team"] if row["home_win_pct"] >= row["away_win_pct"] else row["away_team"]
    spread = f"{ml} {row['home_puckline']:+}" if ml == row["home_team"] else f"{ml} {row['away_puckline']:+}"
    ou = "Over" if (row["home_Goals_For"] + row["away_Goals_For"]) > row["over_under"] else "Under"
    return ml, spread, ou

def save_pick(row, ml, spread, ou):
    record = {
        "date": today(),
        "away_team": row["away_team"],
        "home_team": row["home_team"],
        "ml_pick": ml,
        "spread_pick": spread,
        "ou_pick": ou
    }

    for path in [CURRENT_PICKS, ARCHIVE]:
        if os.path.exists(path):
            df = pd.read_csv(path)
            df = pd.concat([df, pd.DataFrame([record])])
        else:
            df = pd.DataFrame([record])
        df.to_csv(path, index=False)

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    df = load_games()
    incoming = request.values.get("Body", "")

    resp = MessagingResponse()
    msg = resp.message()

    if df.empty:
        msg.body("No NHL games loaded for today.")
        return str(resp)

    game = find_game(df, incoming)
    if game is None:
        msg.body("Team not found. Try Bruins, Rangers, Leafs.")
        return str(resp)

    ml, spread, ou = decide(game)
    save_pick(game, ml, spread, ou)

    msg.body(
        f"🏒 NHL PICK ({today()})\n\n"
        f"{game['away_team']} @ {game['home_team']}\n\n"
        f"💰 ML: {ml}\n"
        f"📈 Spread: {spread}\n"
        f"⚖️ O/U: {ou}"
    )
    return str(resp)

@app.route("/")
def home():
    return "NHL WhatsApp bot live."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
