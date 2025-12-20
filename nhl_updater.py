import pandas as pd
from datetime import date
import os

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(DATA_DIR, "nhl_tonight_model_ready.csv")

# -----------------------------
# Example: generate today's games
# Replace with your model logic
# -----------------------------
games = [
    {"game_date": date.today(), "away_team": "Bruins", "home_team": "Maple Leafs",
     "home_win_pct": 0.6, "away_win_pct": 0.4, "goal_diff_matchup": 1,
     "home_Goals_For": 3, "away_Goals_For": 2, "home_puckline": -1.5,
     "away_puckline": 1.5, "over_under": 5.5},
    {"game_date": date.today(), "away_team": "Rangers", "home_team": "Islanders",
     "home_win_pct": 0.55, "away_win_pct": 0.45, "goal_diff_matchup": -1,
     "home_Goals_For": 2.5, "away_Goals_For": 3, "home_puckline": -1.0,
     "away_puckline": 1.0, "over_under": 6},
]

df = pd.DataFrame(games)
df.to_csv(OUTPUT_CSV, index=False)

print("✅ Updated games CSV created at:", OUTPUT_CSV)
print("Rows:", len(df))
