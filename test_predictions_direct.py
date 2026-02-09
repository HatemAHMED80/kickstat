"""Test predictions endpoint directly."""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating

# Load training data
print("Loading training data...")
ligue1_matches_raw = load_historical_data("ligue_1", [2024])
pl_matches_raw = load_historical_data("premier_league", [2024])
all_matches_raw = ligue1_matches_raw + pl_matches_raw

print(f"Loaded {len(all_matches_raw)} matches")
print(f"First match type: {type(all_matches_raw[0])}")
print(f"First match keys: {all_matches_raw[0].keys() if isinstance(all_matches_raw[0], dict) else 'Not a dict'}")

# Convert to MatchResult
print("\nConverting to MatchResult objects...")
all_matches = [
    MatchResult(
        home_team=m["home_team"],
        away_team=m["away_team"],
        home_goals=m["home_score"],
        away_goals=m["away_score"],
        date=m["kickoff"],
    )
    for m in all_matches_raw
]

print(f"Converted {len(all_matches)} matches")
print(f"First match type: {type(all_matches[0])}")

# Train Dixon-Coles
print("\nTraining Dixon-Coles...")
dc_model = DixonColesModel(half_life_days=180)
dc_model.fit(all_matches)
print(f"DC model trained with {len(dc_model.teams)} teams")

# Train ELO
print("\nTraining ELO...")
elo_model = EloRating(k_factor=20, home_advantage=100)
for match in all_matches:
    elo_model.update(match)
print(f"ELO model trained")

# Test prediction
print("\nTesting prediction...")
try:
    dc_pred = dc_model.predict("PSG", "Marseille")
    print(f"DC prediction: H={dc_pred.home_win:.3f}, D={dc_pred.draw:.3f}, A={dc_pred.away_win:.3f}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

try:
    elo_pred = elo_model.predict("PSG", "Marseille")
    print(f"ELO prediction: H={elo_pred['home']:.3f}, D={elo_pred['draw']:.3f}, A={elo_pred['away']:.3f}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\nSuccess!")
