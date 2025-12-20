import pandas as pd
from datetime import datetime

# -----------------------------
# File paths
# -----------------------------
PICKS_CSV = "nhl_tonight_model_ready.csv"  # your uploaded CSV
OUTPUT_CSV = "nhl_results_vs_picks.csv"    # final output CSV

# -----------------------------
# 1. Load picks CSV
# -----------------------------
try:
    picks_df = pd.read_csv(PICKS_CSV)
    print(f"Loaded {len(picks_df)} rows from {PICKS_CSV}")
except Exception as e:
    print(f"Error loading picks CSV: {e}")
    picks_df = pd.DataFrame()

# -----------------------------
# 2. Scrape NHL results from Hockey Reference
# -----------------------------
url_results = "https://www.hockey-reference.com/leagues/NHL_2026_games.html"

try:
    tables = pd.read_html(url_results)
    results_df = pd.concat(tables, ignore_index=True)
    print("Scraped columns:", results_df.columns.tolist())

    # Rename columns to match our merge keys
    results_df = results_df.rename(columns={
        'Visitor': 'away_team',
        'Home': 'home_team',
        'G': 'away_goals',
        'G.1': 'home_goals'
    })

    # Keep only relevant columns
    results_df = results_df[['away_team', 'home_team', 'away_goals', 'home_goals']]

    # Remove any header rows repeated mid-season
    results_df = results_df[results_df['away_goals'].apply(lambda x: str(x).isdigit())]

    # Convert goals to numeric
    results_df['away_goals'] = pd.to_numeric(results_df['away_goals'], errors='coerce')
    results_df['home_goals'] = pd.to_numeric(results_df['home_goals'], errors='coerce')

    # Strip whitespace from team names
    results_df['away_team'] = results_df['away_team'].str.strip()
    results_df['home_team'] = results_df['home_team'].str.strip()

    print(f"Processed {len(results_df)} valid games from Hockey Reference")

except Exception as e:
    print(f"Error scraping results: {e}")
    results_df = pd.DataFrame()

# -----------------------------
# 3. Merge picks with results
# -----------------------------
if not picks_df.empty and not results_df.empty:
    merged = picks_df.merge(results_df, on=['away_team', 'home_team'], how='left')
else:
    merged = picks_df.copy()
    merged['away_goals'] = None
    merged['home_goals'] = None

# -----------------------------
# 4. Evaluate ML, Spread, O/U
# -----------------------------
def evaluate(row):
    try:
        # Moneyline
        if pd.notna(row['home_goals']) and pd.notna(row['away_goals']):
            if row['home_goals'] > row['away_goals']:
                ml_winner = row['home_team']
            elif row['home_goals'] < row['away_goals']:
                ml_winner = row['away_team']
            else:
                ml_winner = "Tie"
            row['ml_correct'] = (row.get('home_moneyline_pick', ml_winner) == ml_winner)
        else:
            row['ml_correct'] = None

        # Spread
        try:
            spread_line = row.get('home_puckline', 0)
            home_margin = row['home_goals'] - row['away_goals']
            row['spread_correct'] = (home_margin + spread_line > 0) if pd.notna(home_margin) else None
        except:
            row['spread_correct'] = None

        # Over/Under
        try:
            total_goals = row['home_goals'] + row['away_goals'] if pd.notna(row['home_goals']) else None
            ou_line = row.get('over_under', 6)
            ou_pick = row.get('ou_pick', 'Over')
            if total_goals is not None:
                if ou_pick == 'Over':
                    row['ou_correct'] = total_goals > ou_line
                else:
                    row['ou_correct'] = total_goals < ou_line
            else:
                row['ou_correct'] = None
        except:
            row['ou_correct'] = None

    except Exception as e:
        print(f"Error evaluating row: {e}")
        row['ml_correct'] = None
        row['spread_correct'] = None
        row['ou_correct'] = None

    return row

merged = merged.apply(evaluate, axis=1)

# -----------------------------
# 5. Add timestamp and save
# -----------------------------
merged['evaluated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
merged.to_csv(OUTPUT_CSV, index=False)
print(f"Saved merged picks + results to {OUTPUT_CSV}")
