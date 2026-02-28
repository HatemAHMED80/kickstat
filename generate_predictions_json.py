"""Generate predictions for upcoming matches across all leagues and export as JSON for web dashboard.

Supports:
- 5 domestic leagues: Premier League, Ligue 1, La Liga, Bundesliga, Serie A
- 3 European competitions: Champions League, Europa League, Conference League
  (European matches use cross-league ELO; domestic matches use full pipeline)
"""

import os
import sys
import json
import pickle

# Force UTF-8 stdout on Windows to handle non-ASCII team names (e.g. Białystok, Plzeň)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data
from src.data.fixtures_api import fetch_tomorrow_fixtures, fetch_today_fixtures, fetch_date_fixtures, fetch_fixtures
from src.data.odds_api import OddsAPIClient, extract_best_odds, remove_margin
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.ensemble import EnsemblePredictor
from src.models.features import MatchHistory, compute_features
from src.models.xgb_model import XGBStackingModel
from src.models.bandit import ContextualBandit

import numpy as np
from sklearn.isotonic import IsotonicRegression

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOMESTIC_LEAGUES = ["premier_league", "ligue_1", "la_liga", "bundesliga", "serie_a"]
EUROPEAN_COMPETITIONS = ["champions_league", "europa_league", "conference_league"]
ALL_LEAGUES = DOMESTIC_LEAGUES + EUROPEAN_COMPETITIONS

# Seasons to load for training (football-data.co.uk has these for all top 5)
TRAINING_SEASONS = [2021, 2022, 2023, 2024, 2025]

# Default ELO for teams not in any top-5 domestic league (UECL/UEL level teams)
# Average rating for a team that regularly qualifies for European competition
DEFAULT_ELO_NONLEAGUE = 1380

# Human-readable league names
LEAGUE_DISPLAY_NAMES = {
    "premier_league": "Premier League",
    "ligue_1": "Ligue 1",
    "la_liga": "La Liga",
    "bundesliga": "Bundesliga",
    "serie_a": "Serie A",
    "champions_league": "Champions League",
    "europa_league": "Europa League",
    "conference_league": "Conference League",
}

# Markets available via The Odds API (eu region, h2h + totals + spreads).
# BTTS, Double Chance, Draw No Bet are NOT available in any region — excluded.
# Away market disabled: -11% to -16% ROI across ALL configs in 5-year backtest.
MARKET_EDGE_THRESHOLDS = {
    # 1X2
    'home': 9999.0,  # DISABLED: home market loses money in 4/5 leagues (model overestimates home advantage)
    'draw': 5.0,
    'away': 9999.0,  # DISABLED: away market loses money in all configurations
    # Over/Under (from totals market)
    'over15': 5.0,
    'under15': 5.0,
    'over25': 5.0,
    'under25': 5.0,
    'over35': 5.0,
    'under35': 5.0,
    # Spreads/Handicap (from spreads market — sometimes available)
    'spread_home_m15': 5.0,
    'spread_away_p15': 5.0,
    'spread_home_m25': 5.0,
    'spread_away_p25': 5.0,
}

# Minimum model probability to recommend a bet (filters out low-prob/high-edge flukes)
MARKET_MIN_PROB = {
    # 1X2
    'home': 0.38,
    'draw': 0.25,
    'away': 0.40,  # (disabled anyway)
    # Over/Under
    'over15': 0.65,
    'under15': 0.40,
    'over25': 0.55,
    'under25': 0.45,
    'over35': 0.45,
    'under35': 0.55,
    # Spreads (handicap — harder to win)
    'spread_home_m15': 0.35,
    'spread_away_p15': 0.55,
    'spread_home_m25': 0.25,
    'spread_away_p25': 0.65,
}

MIN_KELLY_STAKE = 1.0  # Minimum Kelly stake % to recommend a bet

# Cache settings
MODELS_CACHE_DIR = PROJECT_ROOT / "models"
CACHE_MAX_AGE_HOURS = 24  # Re-train if cache is older than this


# ---------------------------------------------------------------------------
# Model cache (pickle)
# ---------------------------------------------------------------------------

def _cache_path(league: str) -> Path:
    return MODELS_CACHE_DIR / f"{league}_bundle.pkl"


def save_bundles(bundles: dict) -> None:
    """Save all trained bundles to disk."""
    MODELS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for league, bundle in bundles.items():
        path = _cache_path(league)
        with open(path, 'wb') as f:
            pickle.dump(bundle, f)
    print(f"[OK] Modeles sauvegardes dans {MODELS_CACHE_DIR}/")


def load_cached_bundles() -> dict:
    """Load bundles from cache if fresh enough (< CACHE_MAX_AGE_HOURS old).

    Returns a dict of whatever is cached and fresh. Leagues missing or stale
    will be absent from the dict and must be (re)trained.
    """
    bundles = {}
    for league in DOMESTIC_LEAGUES:
        path = _cache_path(league)
        if not path.exists():
            continue
        age_hours = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 3600
        if age_hours > CACHE_MAX_AGE_HOURS:
            continue
        try:
            with open(path, 'rb') as f:
                bundles[league] = pickle.load(f)
        except Exception:
            continue
    return bundles


# ---------------------------------------------------------------------------
# LeagueModelBundle — one per domestic league
# ---------------------------------------------------------------------------

@dataclass
class LeagueModelBundle:
    """All models trained on a single domestic league."""
    league: str
    dc_model: DixonColesModel
    elo_model: EloRating
    xgb_model: XGBStackingModel
    bandit: ContextualBandit
    history: MatchHistory
    teams: set = field(default_factory=set)
    calibrators: dict = field(default_factory=dict)  # market -> IsotonicRegression


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def _train_calibrators(dc_model: DixonColesModel, matches_data: list, min_samples: int = 80) -> dict:
    """Fit isotonic regression calibrators for DC model probabilities.

    Uses the last 30% of historical matches (temporal split) to avoid
    fitting on the same data the DC model was trained on.

    Returns dict: market -> IsotonicRegression (or empty dict if insufficient data).
    """
    n = len(matches_data)
    cal_start = max(200, int(n * 0.70))
    cal_matches = matches_data[cal_start:]

    if len(cal_matches) < min_samples:
        return {}

    markets = ('over15', 'over25', 'over35', 'btts_yes', 'home_win', 'draw_win', 'away_win')
    preds_map = {k: [] for k in markets}
    actuals_map = {k: [] for k in markets}

    for md in cal_matches:
        try:
            pred = dc_model.predict(md['home_team'], md['away_team'])
            hs = int(md['home_score'])
            aws = int(md['away_score'])
            total = hs + aws

            preds_map['over15'].append(pred.over_15)
            actuals_map['over15'].append(1 if total > 1 else 0)

            preds_map['over25'].append(pred.over_25)
            actuals_map['over25'].append(1 if total > 2 else 0)

            preds_map['over35'].append(pred.over_35)
            actuals_map['over35'].append(1 if total > 3 else 0)

            preds_map['btts_yes'].append(pred.btts_yes)
            actuals_map['btts_yes'].append(1 if hs >= 1 and aws >= 1 else 0)

            preds_map['home_win'].append(pred.home_win)
            actuals_map['home_win'].append(1 if hs > aws else 0)

            preds_map['draw_win'].append(pred.draw)
            actuals_map['draw_win'].append(1 if hs == aws else 0)

            preds_map['away_win'].append(pred.away_win)
            actuals_map['away_win'].append(1 if aws > hs else 0)
        except Exception:
            continue

    calibrators = {}
    for market in preds_map:
        p, a = preds_map[market], actuals_map[market]
        if len(p) < min_samples:
            continue
        try:
            cal = IsotonicRegression(out_of_bounds='clip')
            cal.fit(p, a)
            calibrators[market] = cal
        except Exception:
            continue

    return calibrators


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_league_models(league: str) -> LeagueModelBundle:
    """Train DC + ELO + XGBoost + Bandit on one domestic league.

    Returns a LeagueModelBundle with all fitted models.
    """
    print(f"\n{'='*60}")
    print(f" Entrainement: {LEAGUE_DISPLAY_NAMES.get(league, league)}")
    print(f"{'='*60}")

    # 1. Load historical data
    print(" Chargement des donnees historiques...")
    matches_data = load_historical_data(
        league=league,
        seasons=TRAINING_SEASONS,
    )
    print(f"[OK] {len(matches_data)} matchs charges")

    # 2. Build MatchHistory for feature engineering
    history = MatchHistory()
    history.add_matches(matches_data)

    # 3. Convert to MatchResult for Dixon-Coles
    matches = []
    teams = set()
    for md in matches_data:
        matches.append(MatchResult(
            date=md['kickoff'],
            home_team=md['home_team'],
            away_team=md['away_team'],
            home_goals=int(md['home_score']),
            away_goals=int(md['away_score']),
        ))
        teams.add(md['home_team'])
        teams.add(md['away_team'])

    # 4. Dixon-Coles
    print(" Entrainement Dixon-Coles...")
    dc_model = DixonColesModel()
    dc_model.fit(matches)
    print(f"[OK] Dixon-Coles entraine sur {len(matches)} matchs")

    # 5. ELO
    print(" Entrainement ELO...")
    elo_model = EloRating(k_factor=20, home_advantage=100)
    for m in matches:
        elo_model.update(EloMatch(
            home_team=m.home_team,
            away_team=m.away_team,
            home_goals=m.home_goals,
            away_goals=m.away_goals,
        ))
    print(f"[OK] ELO entraine - {len(elo_model.ratings)} equipes")

    # 6. XGBoost stacking
    print(" Entrainement XGBoost (stacking)...")
    xgb_model = XGBStackingModel()

    X_list, y_list = [], []
    for i, md in enumerate(matches_data):
        if i < 200:
            continue
        try:
            features = compute_features(
                home_team=md['home_team'],
                away_team=md['away_team'],
                match_date=md['kickoff'],
                history=history,
                dc_model=dc_model,
                elo_model=elo_model,
            )
            hs, as_ = int(md['home_score']), int(md['away_score'])
            outcome = 0 if hs > as_ else (1 if hs == as_ else 2)

            from src.models.features import features_to_array
            X_list.append(features_to_array(features))
            y_list.append(outcome)
        except Exception:
            continue

    if X_list:
        X = np.vstack(X_list)
        y = np.array(y_list)
        split_idx = int(len(X) * 0.8)
        xgb_model.fit(X[:split_idx], y[:split_idx], X[split_idx:], y[split_idx:])
        if xgb_model.is_fitted:
            print(f"[OK] XGBoost entraine sur {split_idx} matchs (val: {len(X)-split_idx})")
        else:
            print(f"[WARNING] XGBoost non entraine")
    else:
        print("[WARNING] Pas de donnees pour XGBoost")

    # 7. Contextual Bandit
    print(" Entrainement Bandit (Thompson Sampling)...")
    bandit = ContextualBandit()
    bandit.fit(matches_data, dc_model=dc_model, elo_model=elo_model)
    if bandit.is_fitted:
        segments = bandit.get_segment_summary()
        print(f"[OK] Bandit entraine - {len(segments)} segments")
    else:
        print("[WARNING] Bandit non entraine")

    # 8. Isotonic calibration for DC over/under and BTTS probabilities
    print(" Calibration isotonique (O/U + BTTS)...")
    calibrators = _train_calibrators(dc_model, matches_data)
    if calibrators:
        print(f"[OK] Calibrateurs: {list(calibrators.keys())} ({len(matches_data) - max(200, int(len(matches_data)*0.70))} matchs)")
    else:
        print("[WARNING] Pas assez de donnees pour calibrer")

    return LeagueModelBundle(
        league=league,
        dc_model=dc_model,
        elo_model=elo_model,
        xgb_model=xgb_model,
        bandit=bandit,
        history=history,
        teams=teams,
        calibrators=calibrators,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_league_for_team(team: str, bundles: dict[str, LeagueModelBundle]) -> Optional[str]:
    """Find which domestic league a team belongs to."""
    for league, bundle in bundles.items():
        if team in bundle.teams:
            return league
    # Fuzzy match via name normalization (handles Odds API names like "VfB Stuttgart" → "Stuttgart")
    normalized = normalize_team_name_for_matching(team)
    for league, bundle in bundles.items():
        for canonical in bundle.teams:
            if normalize_team_name_for_matching(canonical) == normalized:
                return league
    return None


def resolve_team_canonical(team: str, bundles: dict[str, LeagueModelBundle]) -> str:
    """Resolve an Odds API team name to the canonical name used in our models.

    Returns the canonical name if found in any bundle, otherwise returns team as-is.
    """
    for bundle in bundles.values():
        if team in bundle.teams:
            return team
    normalized = normalize_team_name_for_matching(team)
    for bundle in bundles.values():
        for canonical in bundle.teams:
            if normalize_team_name_for_matching(canonical) == normalized:
                return canonical
    return team


def calculate_kelly_stake(prob, odds, fraction=0.25):
    """Calculate Kelly Criterion stake."""
    if odds <= 1.0:
        return 0.0
    b = odds - 1
    q = 1 - prob
    kelly = (b * prob - q) / b
    return max(0, kelly * fraction * 100)


def determine_segment(prob):
    """Determine market segment based on probability."""
    if prob >= 0.60:
        return "Heavy Favorite"
    elif prob >= 0.50:
        return "Favorite"
    elif prob >= 0.35:
        return "Balanced"
    else:
        return "Underdog"


def determine_confidence_badge(edge, prob):
    """Determine confidence badge based on probability (primary) and edge (secondary).
    Edge is in decimal form (e.g. 0.088 = 8.8%). Prob is [0,1].
    Tiers match frontend CONFIDENCE_TIERS."""
    # Require at least a positive edge to recommend a bet
    if edge <= 0:
        return None
    # Badge is primarily driven by probability (model confidence)
    if prob >= 0.85:
        return "ULTRA_SAFE"
    elif prob >= 0.75:
        return "HIGH_SAFE"
    elif prob >= 0.60:
        return "SAFE"
    elif prob >= 0.50:
        return "VALUE"
    elif prob >= 0.35:
        return "RISKY"
    else:
        return "ULTRA_RISKY"


def normalize_team_name_for_matching(name):
    """Normalize team names for matching between APIs (all leagues)."""
    if not name:
        return ""

    name = name.lower()
    # Strip common club suffixes (European clubs: BC, SC, SK, TC, FK, BK, etc.)
    for suffix in (' fc', ' afc', ' bc', ' sc', ' sk', ' tc', ' fk', ' bk', ' if', ' aik'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    name = name.replace(' united', '')
    name = name.replace('&', 'and')

    # Common abbreviations across all leagues
    replacements = {
        # Premier League
        'manchester city': 'man city',
        'manchester united': 'man utd',
        'tottenham hotspur': 'tottenham',
        'brighton and hove albion': 'brighton',
        'brighton & hove albion': 'brighton',
        'newcastle united': 'newcastle',
        'west ham united': 'west ham',
        'nottingham forest': "nott'm forest",
        'wolverhampton wanderers': 'wolves',
        'leicester city': 'leicester',
        # Ligue 1
        'paris saint-germain': 'paris sg',
        'paris saint germain': 'paris sg',
        'olympique de marseille': 'marseille',
        'olympique lyonnais': 'lyon',
        'as monaco': 'monaco',
        'stade rennais': 'rennes',
        'rc strasbourg alsace': 'strasbourg',
        'stade brestois': 'brest',
        'stade de reims': 'reims',
        'as saint-etienne': 'st etienne',
        'as saint-étienne': 'st etienne',
        # La Liga
        'atletico de madrid': 'ath madrid',
        'atletico madrid': 'ath madrid',
        'club atletico de madrid': 'ath madrid',
        'athletic club': 'ath bilbao',
        'athletic bilbao': 'ath bilbao',
        'real sociedad de futbol': 'real sociedad',
        'real betis balompie': 'betis',
        'real betis': 'betis',
        'celta de vigo': 'celta',
        'celta vigo': 'celta',
        'rayo vallecano': 'vallecano',
        'deportivo alaves': 'alaves',
        # Bundesliga
        'bayern munich': 'bayern munich',
        'fc bayern munchen': 'bayern munich',
        'borussia dortmund': 'dortmund',
        'bayer 04 leverkusen': 'leverkusen',
        'bayer leverkusen': 'leverkusen',
        'eintracht frankfurt': 'ein frankfurt',
        'sport-club freiburg': 'freiburg',
        'sc freiburg': 'freiburg',
        'borussia monchengladbach': "m'gladbach",
        'vfl wolfsburg': 'wolfsburg',
        'vfb stuttgart': 'stuttgart',
        '1899 hoffenheim': 'hoffenheim',
        'tsg 1899 hoffenheim': 'hoffenheim',
        'sv werder bremen': 'werder bremen',
        'werder bremen': 'werder bremen',
        '1. fc union berlin': 'union berlin',
        'vfl bochum': 'bochum',
        'fc st. pauli': 'st pauli',
        # Serie A
        'fc internazionale milano': 'inter',
        'internazionale': 'inter',
        'ac milan': 'milan',
        'ssc napoli': 'napoli',
        'as roma': 'roma',
        'ss lazio': 'lazio',
        'acf fiorentina': 'fiorentina',
        'bologna fc 1909': 'bologna',
        'hellas verona': 'verona',
        'ac monza': 'monza',
        'us lecce': 'lecce',
        'us sassuolo calcio': 'sassuolo',
        'parma calcio 1913': 'parma',
        'udinese calcio': 'udinese',
        'genoa cfc': 'genoa',
        'cagliari calcio': 'cagliari',
        # European clubs (UCL/UEL/UECL — Odds API names)
        'sport lisboa e benfica': 'benfica',
        'sl benfica': 'benfica',
        'galatasaray': 'galatasaray',
        'atalanta': 'atalanta',
        'nottingham forest': "nott'm forest",
        'nott\'m forest': "nott'm forest",
        'paris saint germain': 'paris sg',
        'as monaco': 'monaco',
        'celta vigo': 'celta',
        'rc celta de vigo': 'celta',
        'red star belgrade': 'red star belgrade',
        'fenerbahce': 'fenerbahce',
        'ajax': 'ajax',
    }

    for full_name, short_name in replacements.items():
        if full_name in name:
            return short_name

    return name.strip()


# ---------------------------------------------------------------------------
# Fixtures & Odds fetching
# ---------------------------------------------------------------------------

def get_fixtures_all_leagues(leagues: list[str] | None = None, today: bool = False, date: str | None = None):
    """Fetch fixtures for all requested leagues (today, tomorrow, or a specific date)."""
    if leagues is None:
        leagues = ALL_LEAGUES

    if date:
        day_label = date
    elif today:
        day_label = "aujourd'hui"
    else:
        day_label = "demain"
    print(f"\n Recuperation des fixtures {day_label} pour {len(leagues)} ligue(s)...")

    try:
        if date:
            fixtures = fetch_date_fixtures(date=date, leagues=leagues)
        elif today:
            fixtures = fetch_today_fixtures(leagues=leagues)
        else:
            # Default: fetch today + tomorrow (catches evening matches + next day)
            from datetime import datetime as _dt, timedelta as _td
            _today = _dt.now().strftime("%Y-%m-%d")
            _tomorrow = (_dt.now() + _td(days=1)).strftime("%Y-%m-%d")
            fixtures = fetch_fixtures(_today, _tomorrow, leagues=leagues)

        # If nothing found, look ahead up to 5 days for next matchday
        if not fixtures and not date and not today:
            from datetime import datetime as _dt, timedelta as _td
            for days_ahead in range(2, 6):
                next_date = (_dt.now() + _td(days=days_ahead)).strftime("%Y-%m-%d")
                fixtures = fetch_date_fixtures(date=next_date, leagues=leagues)
                if fixtures:
                    day_label = next_date
                    print(f"[INFO] Pas de matchs aujourd'hui/demain — prochain jour de match: {next_date}")
                    break

        if not fixtures:
            print(f"[WARNING] Aucun match trouve pour les 5 prochains jours")
            return []
        print(f"[OK] {len(fixtures)} match(s) trouve(s)")
        return fixtures
    except Exception as e:
        print(f"[ERROR] Erreur fixtures: {e}")
        return []


def get_odds_all_leagues(leagues: list[str] | None = None):
    """Fetch real-time odds for all requested leagues.

    Returns a dict mapping league_slug -> list of odds data.
    """
    if leagues is None:
        leagues = ALL_LEAGUES

    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("[WARNING] ODDS_API_KEY non defini, pas de cotes")
        return {}

    print(f"\n Recuperation des cotes pour {len(leagues)} ligue(s)...")
    odds_client = OddsAPIClient(api_key=api_key)

    all_odds = {}
    try:
        for league_slug in leagues:
            try:
                data = odds_client.get_odds(
                    league=league_slug,
                    markets="h2h,totals,spreads",
                    regions="eu",
                )
                if data:
                    all_odds[league_slug] = data
                    print(f"  [OK] {league_slug}: {len(data)} matchs avec cotes")
            except Exception as e:
                print(f"  [WARNING] {league_slug}: {e}")
    finally:
        odds_client.close()

    return all_odds


# ---------------------------------------------------------------------------
# European prediction (cross-league ELO)
# ---------------------------------------------------------------------------

def generate_european_prediction(
    home_team: str,
    away_team: str,
    kickoff: str,
    bundles: dict[str, LeagueModelBundle],
    odds_entry: Optional[dict] = None,
) -> Optional[dict]:
    """Generate a prediction for a European match using cross-league ELO.

    For European matches (UCL/UEL/UECL), we:
    - Find each team's ELO from their domestic league
    - Use a temporary ELO model to predict 1X2
    - Use the home team's DC model for over/under (best available)
    - No XGBoost or Bandit (not trained on cross-league data)
    """
    home_league = get_league_for_team(home_team, bundles)
    away_league = get_league_for_team(away_team, bundles)

    # Skip only if BOTH teams are completely unknown (no data at all)
    if not home_league and not away_league:
        print(f"  [SKIP] Equipes inconnues: {home_team} et {away_team} (aucune ligue top-5)")
        return None

    # Get ELO ratings — use default for non-top-5 teams (UECL/UEL level)
    if home_league:
        home_elo = bundles[home_league].elo_model.get_rating(home_team)
    else:
        home_elo = DEFAULT_ELO_NONLEAGUE
        print(f"  [ELO] {home_team}: hors top-5, ELO par defaut {DEFAULT_ELO_NONLEAGUE}")

    if away_league:
        away_elo = bundles[away_league].elo_model.get_rating(away_team)
    else:
        away_elo = DEFAULT_ELO_NONLEAGUE
        print(f"  [ELO] {away_team}: hors top-5, ELO par defaut {DEFAULT_ELO_NONLEAGUE}")

    elo_estimated = not home_league or not away_league

    # Create temporary ELO with both teams' ratings
    temp_elo = EloRating(k_factor=20, home_advantage=100)
    temp_elo.ratings[home_team] = home_elo
    temp_elo.ratings[away_team] = away_elo

    # ELO-based 1X2 prediction
    elo_pred = temp_elo.predict_1x2(home_team, away_team)

    # Use known team's DC model for over/under and BTTS (prefer home, fallback to away)
    dc_league = home_league or away_league
    home_dc = bundles[dc_league].dc_model
    try:
        dc_pred = home_dc.predict(home_team, away_team)
        has_dc = True
    except Exception:
        has_dc = False

    # Build basic probabilities from ELO (predict_1x2 returns a dict)
    home_prob = elo_pred["home"]
    draw_prob = elo_pred["draw"]
    away_prob = elo_pred["away"]

    # Over/under and BTTS from DC if available
    over15_prob = dc_pred.over_15 if has_dc else None
    over25_prob = dc_pred.over_25 if has_dc else None
    over35_prob = dc_pred.over_35 if has_dc else None
    btts_yes_prob = dc_pred.btts_yes if has_dc else None

    # Apply isotonic calibration from the home team's domestic bundle
    home_bundle = bundles.get(home_league)
    if home_bundle and getattr(home_bundle, 'calibrators', {}):
        cals = getattr(home_bundle, 'calibrators', {})
        if over15_prob is not None and 'over15' in cals:
            over15_prob = float(cals['over15'].predict([over15_prob])[0])
        if over25_prob is not None and 'over25' in cals:
            over25_prob = float(cals['over25'].predict([over25_prob])[0])
        if over35_prob is not None and 'over35' in cals:
            over35_prob = float(cals['over35'].predict([over35_prob])[0])
        if btts_yes_prob is not None and 'btts_yes' in cals:
            btts_yes_prob = float(cals['btts_yes'].predict([btts_yes_prob])[0])
        if 'home_win' in cals and 'draw_win' in cals and 'away_win' in cals:
            h = float(cals['home_win'].predict([home_prob])[0])
            d = float(cals['draw_win'].predict([draw_prob])[0])
            a = float(cals['away_win'].predict([away_prob])[0])
            total = h + d + a
            if total > 0:
                home_prob, draw_prob, away_prob = h / total, d / total, a / total

    # Double Chance
    dc_1x_prob = home_prob + draw_prob
    dc_x2_prob = draw_prob + away_prob
    dc_12_prob = home_prob + away_prob

    # Draw No Bet
    dnb_home_prob = home_prob / (home_prob + away_prob) if (home_prob + away_prob) > 0 else None
    dnb_away_prob = away_prob / (home_prob + away_prob) if (home_prob + away_prob) > 0 else None

    # Spreads from DC score matrix
    # DISABLED for European matches when away team ELO is estimated:
    # DC model trained on home team's domestic league vs average opponent — not reliable vs unknown European teams
    spread_home_m15_prob = None
    spread_away_p15_prob = None
    spread_home_m25_prob = None
    spread_away_p25_prob = None
    if has_dc and not elo_estimated and hasattr(dc_pred, 'score_matrix') and dc_pred.score_matrix is not None:
        matrix = dc_pred.score_matrix
        n = matrix.shape[0]
        hm15 = sum(matrix[i][j] for i in range(n) for j in range(n) if i - j >= 2)
        spread_home_m15_prob = hm15
        spread_away_p15_prob = 1.0 - hm15
        hm25 = sum(matrix[i][j] for i in range(n) for j in range(n) if i - j >= 3)
        spread_home_m25_prob = hm25
        spread_away_p25_prob = 1.0 - hm25

    # BTTS unreliable when away team is estimated (depends on both teams scoring)
    if elo_estimated:
        btts_yes_prob = None

    # Market probs for betting (only markets with real odds)
    extra_probs = dict(
        over15_prob=over15_prob,
        over25_prob=over25_prob,
        over35_prob=over35_prob,
        spread_home_m15_prob=spread_home_m15_prob, spread_away_p15_prob=spread_away_p15_prob,
        spread_home_m25_prob=spread_home_m25_prob, spread_away_p25_prob=spread_away_p25_prob,
    )

    # Odds and edge calculation
    best_odds, bookmaker, edge = _default_odds_and_edge(home_prob, draw_prob, away_prob)

    if odds_entry:
        best_odds, bookmaker, edge = _extract_odds_and_edge(
            odds_entry, home_prob, draw_prob, away_prob, **extra_probs
        )

    # Recommendation (same logic as domestic)
    recommended_bet, kelly_stake, quality_score, confidence_badge = _compute_recommendation(
        home_prob, draw_prob, away_prob, best_odds, edge, **extra_probs
    )

    max_prob = max(home_prob, draw_prob, away_prob)

    prediction = {
        'match_id': f"{home_team.lower().replace(' ', '_')}_vs_{away_team.lower().replace(' ', '_')}_{kickoff[:10] if kickoff else ''}",
        'home_team': home_team,
        'away_team': away_team,
        'kickoff': kickoff,
        'model_probs': {
            'home': round(home_prob, 3),
            'draw': round(draw_prob, 3),
            'away': round(away_prob, 3),
        },
        'best_odds': {k: round(v, 2) for k, v in best_odds.items()},
        'bookmaker': bookmaker,
        'edge': {k: round(v * 100, 1) for k, v in edge.items()},
        'recommended_bet': recommended_bet,
        'kelly_stake': round(kelly_stake, 1),
        'segment': determine_segment(max_prob),
        'quality_score': round(quality_score, 1) if quality_score else None,
        'confidence_badge': confidence_badge,
        'is_european': True,
        'prediction_source': 'elo_estimated' if elo_estimated else 'elo_cross_league',
        'bandit_recommendation': None,
    }

    # Over/under and BTTS from DC if available (using calibrated probs)
    if has_dc:
        prediction['over_under_15'] = {
            'over_15': round(over15_prob, 3) if over15_prob is not None else None,
            'under_15': round(1 - over15_prob, 3) if over15_prob is not None else None,
        }
        prediction['over_under'] = {
            'over_25': round(over25_prob, 3) if over25_prob is not None else None,
            'under_25': round(1 - over25_prob, 3) if over25_prob is not None else None,
        }
        prediction['over_under_35'] = {
            'over_35': round(over35_prob, 3) if over35_prob is not None else None,
            'under_35': round(1 - over35_prob, 3) if over35_prob is not None else None,
        }
        prediction['btts'] = {
            'yes': round(btts_yes_prob, 3) if btts_yes_prob is not None else None,
            'no': round(1 - btts_yes_prob, 3) if btts_yes_prob is not None else None,
        }
        prediction['correct_score'] = None
    else:
        prediction['over_under_15'] = None
        prediction['over_under'] = None
        prediction['over_under_35'] = None
        prediction['btts'] = None
        prediction['correct_score'] = None

    # Double Chance, DNB, Spreads (always available from 1X2 probs)
    prediction['double_chance'] = {
        '1x': round(dc_1x_prob, 3),
        'x2': round(dc_x2_prob, 3),
        '12': round(dc_12_prob, 3),
    }
    prediction['draw_no_bet'] = {
        'home': round(dnb_home_prob, 3) if dnb_home_prob else None,
        'away': round(dnb_away_prob, 3) if dnb_away_prob else None,
    }
    prediction['spreads'] = {
        'home_m15': round(spread_home_m15_prob, 3) if spread_home_m15_prob else None,
        'home_m25': round(spread_home_m25_prob, 3) if spread_home_m25_prob else None,
    }

    return prediction


# ---------------------------------------------------------------------------
# Recent form helper
# ---------------------------------------------------------------------------

def _build_team_recent_stats(team: str, history: MatchHistory, match_date) -> dict:
    """Return last-5 match stats + aggregated stats for the front-end."""
    matches = history.get_team_matches(team, before_date=match_date, last_n=5)
    recent = []
    pts, gf_list, ga_list, shots_list, sot_list, corners_list, opp_sot_list = [], [], [], [], [], [], []

    for m, is_home in matches:
        hs = m.get("home_score", 0)
        as_ = m.get("away_score", 0)
        if is_home:
            gf, ga = hs, as_
            opponent = m["away_team"]
            home_away = "home"
            shots = m.get("hs", 0)
            sot = m.get("hst", 0)
            corners = m.get("hc", 0)
            opp_sot = m.get("ast", 0)
        else:
            gf, ga = as_, hs
            opponent = m["home_team"]
            home_away = "away"
            shots = m.get("as", 0)
            sot = m.get("ast", 0)
            corners = m.get("ac", 0)
            opp_sot = m.get("hst", 0)

        result = "win" if gf > ga else ("draw" if gf == ga else "loss")
        point = 3 if result == "win" else (1 if result == "draw" else 0)
        kickoff = m.get("kickoff")
        date_str = kickoff.strftime("%d/%m/%y") if hasattr(kickoff, "strftime") else str(kickoff)[:10]

        recent.append({
            "date": date_str,
            "opponent": opponent,
            "score": f"{gf}-{ga}",
            "result": result,
            "home_away": home_away,
            "clean_sheet": ga == 0,
        })
        pts.append(point)
        gf_list.append(gf)
        ga_list.append(ga)
        shots_list.append(shots)
        sot_list.append(sot)
        corners_list.append(corners)
        opp_sot_list.append(opp_sot)

    n = len(matches) or 1
    avg_shots = sum(shots_list) / n
    avg_sot = sum(sot_list) / n
    total_sot = sum(sot_list) + sum(opp_sot_list)
    dominance = sum(sot_list) / total_sot if total_sot > 0 else 0.5

    return {
        "ppg": round(sum(pts) / n, 2),
        "goals_scored_avg": round(sum(gf_list) / n, 2),
        "goals_conceded_avg": round(sum(ga_list) / n, 2),
        "shots_per_game": round(avg_shots, 1),
        "shots_on_target_per_game": round(avg_sot, 1),
        "shot_accuracy": round(avg_sot / avg_shots * 100, 1) if avg_shots > 0 else 0,
        "corners_per_game": round(sum(corners_list) / n, 1),
        "dominance_score": round(dominance, 3),
        "recent_form": "".join(["W" if r["result"] == "win" else ("D" if r["result"] == "draw" else "L") for r in recent]),
        "recent_matches": recent,
    }


# ---------------------------------------------------------------------------
# Domestic prediction (full pipeline: DC + ELO + XGBoost + Bandit)
# ---------------------------------------------------------------------------

def generate_domestic_prediction(
    home_team: str,
    away_team: str,
    kickoff: str,
    bundle: LeagueModelBundle,
    odds_entry: Optional[dict] = None,
) -> Optional[dict]:
    """Generate a prediction for a domestic match using the full pipeline."""

    dc_model = bundle.dc_model
    elo_model = bundle.elo_model
    xgb_model = bundle.xgb_model
    bandit = bundle.bandit
    history = bundle.history

    # Ensemble predictor
    ensemble = EnsemblePredictor(
        dc_model=dc_model,
        elo_model=elo_model,
        dc_weight=0.65,
        elo_weight=0.35,
        xgb_model=xgb_model if xgb_model.is_fitted else None,
        temperature=1.2 if xgb_model.is_fitted else None,
    )

    # Compute features for XGBoost
    match_features = None
    home_recent_stats: dict = {"recent_matches": []}
    away_recent_stats: dict = {"recent_matches": []}
    try:
        match_date = datetime.fromisoformat(kickoff.replace('Z', '+00:00')) if kickoff else datetime.now()
        # Strip timezone — historical data uses naive datetimes
        match_date = match_date.replace(tzinfo=None)
        home_recent_stats = _build_team_recent_stats(home_team, history, match_date)
        away_recent_stats = _build_team_recent_stats(away_team, history, match_date)
        match_features = compute_features(
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            history=history,
            dc_model=dc_model,
            elo_model=elo_model,
        )
    except Exception as e:
        print(f"  -> Features non calculees: {e}")

    # Model predictions
    pred = ensemble.predict(home_team, away_team, match_features=match_features)
    dc_pred = dc_model.predict(home_team, away_team)

    home_prob = pred.home_prob
    draw_prob = pred.draw_prob
    away_prob = pred.away_prob

    # DC model probabilities for over/under and BTTS
    over15_prob = dc_pred.over_15 if hasattr(dc_pred, 'over_15') else None
    over25_prob = dc_pred.over_25 if hasattr(dc_pred, 'over_25') else None
    over35_prob = dc_pred.over_35 if hasattr(dc_pred, 'over_35') else None
    btts_yes_prob = dc_pred.btts_yes if hasattr(dc_pred, 'btts_yes') else None

    # Apply isotonic calibration (corrects DC model systematic bias)
    cals = getattr(bundle, 'calibrators', {})
    if cals:
        if over15_prob is not None and 'over15' in cals:
            over15_prob = float(cals['over15'].predict([over15_prob])[0])
        if over25_prob is not None and 'over25' in cals:
            over25_prob = float(cals['over25'].predict([over25_prob])[0])
        if over35_prob is not None and 'over35' in cals:
            over35_prob = float(cals['over35'].predict([over35_prob])[0])
        if btts_yes_prob is not None and 'btts_yes' in cals:
            btts_yes_prob = float(cals['btts_yes'].predict([btts_yes_prob])[0])
        # Calibrate 1X2 probabilities independently, then renormalize
        if 'home_win' in cals and 'draw_win' in cals and 'away_win' in cals:
            h = float(cals['home_win'].predict([home_prob])[0])
            d = float(cals['draw_win'].predict([draw_prob])[0])
            a = float(cals['away_win'].predict([away_prob])[0])
            total = h + d + a
            if total > 0:
                home_prob, draw_prob, away_prob = h / total, d / total, a / total

    # Double Chance (from 1X2 probs)
    dc_1x_prob = home_prob + draw_prob
    dc_x2_prob = draw_prob + away_prob
    dc_12_prob = home_prob + away_prob

    # Draw No Bet (conditional: if not draw)
    dnb_home_prob = home_prob / (home_prob + away_prob) if (home_prob + away_prob) > 0 else None
    dnb_away_prob = away_prob / (home_prob + away_prob) if (home_prob + away_prob) > 0 else None

    # Spreads/Handicap from DC score matrix
    spread_home_m15_prob = None
    spread_away_p15_prob = None
    spread_home_m25_prob = None
    spread_away_p25_prob = None
    if hasattr(dc_pred, 'score_matrix') and dc_pred.score_matrix is not None:
        matrix = dc_pred.score_matrix
        n = matrix.shape[0]
        # Home -1.5 = home wins by 2+ goals
        hm15 = sum(matrix[i][j] for i in range(n) for j in range(n) if i - j >= 2)
        spread_home_m15_prob = hm15
        spread_away_p15_prob = 1.0 - hm15
        # Home -2.5 = home wins by 3+ goals
        hm25 = sum(matrix[i][j] for i in range(n) for j in range(n) if i - j >= 3)
        spread_home_m25_prob = hm25
        spread_away_p25_prob = 1.0 - hm25

    # Market probs for betting (only markets with real odds)
    extra_probs = dict(
        over15_prob=over15_prob,
        over25_prob=over25_prob,
        over35_prob=over35_prob,
        spread_home_m15_prob=spread_home_m15_prob, spread_away_p15_prob=spread_away_p15_prob,
        spread_home_m25_prob=spread_home_m25_prob, spread_away_p25_prob=spread_away_p25_prob,
    )

    # Odds and edge
    best_odds, bookmaker, edge = _default_odds_and_edge(home_prob, draw_prob, away_prob)

    if odds_entry:
        best_odds, bookmaker, edge = _extract_odds_and_edge(
            odds_entry, home_prob, draw_prob, away_prob, **extra_probs
        )

    # Recommendation
    recommended_bet, kelly_stake, quality_score, confidence_badge = _compute_recommendation(
        home_prob, draw_prob, away_prob, best_odds, edge, **extra_probs
    )

    max_prob = max(home_prob, draw_prob, away_prob)

    # Correct score from DC
    correct_score = {}
    if hasattr(dc_pred, 'score_probs') and dc_pred.score_probs:
        for sp in dc_pred.score_probs[:5]:
            correct_score[sp['score']] = sp['prob'] / 100.0

    prediction = {
        'match_id': f"{home_team.lower().replace(' ', '_')}_vs_{away_team.lower().replace(' ', '_')}_{kickoff[:10] if kickoff else ''}",
        'home_team': home_team,
        'away_team': away_team,
        'kickoff': kickoff,
        'model_probs': {
            'home': round(home_prob, 3),
            'draw': round(draw_prob, 3),
            'away': round(away_prob, 3),
        },
        'best_odds': {k: round(v, 2) for k, v in best_odds.items()},
        'bookmaker': bookmaker,
        'edge': {k: round(v * 100, 1) for k, v in edge.items()},
        'recommended_bet': recommended_bet,
        'kelly_stake': round(kelly_stake, 1),
        'segment': determine_segment(max_prob),
        'quality_score': round(quality_score, 1) if quality_score else None,
        'confidence_badge': confidence_badge,
        'is_european': False,
        'prediction_source': 'full_pipeline',
        'over_under_15': {
            'over_15': round(over15_prob, 3) if over15_prob is not None else None,
            'under_15': round(1 - over15_prob, 3) if over15_prob is not None else None,
        },
        'over_under': {
            'over_25': round(over25_prob, 3) if over25_prob is not None else None,
            'under_25': round(1 - over25_prob, 3) if over25_prob is not None else None,
        },
        'over_under_35': {
            'over_35': round(over35_prob, 3) if over35_prob is not None else None,
            'under_35': round(1 - over35_prob, 3) if over35_prob is not None else None,
        },
        'btts': {
            'yes': round(btts_yes_prob, 3) if btts_yes_prob is not None else None,
            'no': round(1 - btts_yes_prob, 3) if btts_yes_prob is not None else None,
        },
        'correct_score': correct_score if correct_score else None,
        'double_chance': {
            '1x': round(dc_1x_prob, 3),
            'x2': round(dc_x2_prob, 3),
            '12': round(dc_12_prob, 3),
        },
        'draw_no_bet': {
            'home': round(dnb_home_prob, 3) if dnb_home_prob else None,
            'away': round(dnb_away_prob, 3) if dnb_away_prob else None,
        },
        'spreads': {
            'home_m15': round(spread_home_m15_prob, 3) if spread_home_m15_prob else None,
            'home_m25': round(spread_home_m25_prob, 3) if spread_home_m25_prob else None,
        },
        'bandit_recommendation': None,
    }

    # Bandit recommendation
    if bandit.is_fitted:
        bandit_ctx = {
            "home_prob": home_prob,
            "draw_prob": draw_prob,
            "away_prob": away_prob,
            "over25_prob": over25_prob or 0.0,
            "btts_prob": btts_yes_prob or 0.0,
            "edge_1x2_home": edge['home'],
            "edge_1x2_draw": edge['draw'],
            "edge_1x2_away": edge['away'],
            "edge_over25": 0.0,
            "edge_under25": 0.0,
            "edge_skip": 0.0,
            "max_edge": max(edge['home'], edge['draw'], edge['away']),
        }
        rec = bandit.recommend(bandit_ctx)
        prediction['bandit_recommendation'] = {
            'market': rec['recommended_market'],
            'confidence': rec['confidence'],
            'segment': rec['segment'],
            'scores': rec['all_scores'],
        }

    prediction['home_stats'] = home_recent_stats
    prediction['away_stats'] = away_recent_stats

    return prediction


# ---------------------------------------------------------------------------
# Shared odds & recommendation helpers
# ---------------------------------------------------------------------------

def _default_odds_and_edge(home_prob, draw_prob, away_prob):
    """Return default (estimated) odds and zero edge when no real odds."""
    best_odds = {
        'home': 1 / home_prob if home_prob > 0 else 10.0,
        'draw': 1 / draw_prob if draw_prob > 0 else 10.0,
        'away': 1 / away_prob if away_prob > 0 else 10.0,
    }
    bookmaker = {'home': 'Estimated', 'draw': 'Estimated', 'away': 'Estimated'}
    edge = {'home': 0.0, 'draw': 0.0, 'away': 0.0}
    return best_odds, bookmaker, edge


def _extract_odds_and_edge(odds_entry, home_prob, draw_prob, away_prob,
                           over15_prob=None, over25_prob=None, over35_prob=None,
                           spread_home_m15_prob=None, spread_away_p15_prob=None,
                           spread_home_m25_prob=None, spread_away_p25_prob=None):
    """Extract best odds and edge from an Odds API entry.

    Handles markets available in eu region: h2h (1X2), totals (O/U), spreads.
    Double Chance, Draw No Bet are not available and excluded.
    """
    best_odds_raw = extract_best_odds(odds_entry)

    best_odds = {
        'home': best_odds_raw['home']['odds'],
        'draw': best_odds_raw['draw']['odds'],
        'away': best_odds_raw['away']['odds'],
    }
    bookmaker = {
        'home': best_odds_raw['home']['bookmaker'],
        'draw': best_odds_raw['draw']['bookmaker'],
        'away': best_odds_raw['away']['bookmaker'],
    }

    # Remove margin for fair 1X2 odds
    fair_probs = remove_margin(best_odds['home'], best_odds['draw'], best_odds['away'])

    edge = {
        'home': home_prob - fair_probs['home'],
        'draw': draw_prob - fair_probs['draw'],
        'away': away_prob - fair_probs['away'],
    }

    def _add_market(key, model_prob):
        odds_val = best_odds_raw[key]['odds']
        if odds_val > 1.0 and model_prob is not None:
            best_odds[key] = odds_val
            bookmaker[key] = best_odds_raw[key]['bookmaker']
            edge[key] = model_prob - (1.0 / odds_val)

    # Over/Under (totals market)
    _add_market('over15', over15_prob)
    _add_market('under15', (1.0 - over15_prob) if over15_prob is not None else None)
    _add_market('over25', over25_prob)
    _add_market('under25', (1.0 - over25_prob) if over25_prob is not None else None)
    _add_market('over35', over35_prob)
    _add_market('under35', (1.0 - over35_prob) if over35_prob is not None else None)

    # Spreads/Handicap (sometimes available)
    _add_market('spread_home_m15', spread_home_m15_prob)
    _add_market('spread_away_p15', spread_away_p15_prob)
    _add_market('spread_home_m25', spread_home_m25_prob)
    _add_market('spread_away_p25', spread_away_p25_prob)

    if all(best_odds.get(k, 0) == 0 for k in ['home', 'draw', 'away']):
        return _default_odds_and_edge(home_prob, draw_prob, away_prob)

    return best_odds, bookmaker, edge


def _compute_recommendation(home_prob, draw_prob, away_prob, best_odds, edge,
                            over15_prob=None, over25_prob=None, over35_prob=None,
                            spread_home_m15_prob=None, spread_away_p15_prob=None,
                            spread_home_m25_prob=None, spread_away_p25_prob=None):
    """Compute recommended bet, kelly stake, quality score and badge.

    Considers markets with real odds: 1X2, Over/Under, Spreads.
    Requires both positive edge AND minimum probability to recommend.
    Ranks by EV score (edge * prob) to favor high-confidence bets.
    """
    qualified_bets = []
    probs = {'home': home_prob, 'draw': draw_prob, 'away': away_prob}

    # Add secondary markets if model probs + real odds exist
    secondary = {
        'over15': over15_prob,
        'under15': (1.0 - over15_prob) if over15_prob is not None else None,
        'over25': over25_prob,
        'under25': (1.0 - over25_prob) if over25_prob is not None else None,
        'over35': over35_prob,
        'under35': (1.0 - over35_prob) if over35_prob is not None else None,
        'spread_home_m15': spread_home_m15_prob,
        'spread_away_p15': spread_away_p15_prob,
        'spread_home_m25': spread_home_m25_prob,
        'spread_away_p25': spread_away_p25_prob,
    }
    for key, prob in secondary.items():
        if prob is not None and key in best_odds:
            probs[key] = prob

    all_markets = list(MARKET_EDGE_THRESHOLDS.keys())

    for market in all_markets:
        if market not in edge or market not in best_odds or market not in probs:
            continue
        market_edge = edge[market]
        prob = probs[market]
        threshold = MARKET_EDGE_THRESHOLDS[market] / 100.0
        min_prob = MARKET_MIN_PROB[market]

        # Require BOTH positive edge AND minimum probability
        if market_edge > threshold and prob >= min_prob:
            odds = best_odds[market]
            kelly = calculate_kelly_stake(prob, odds)
            if kelly >= MIN_KELLY_STAKE:
                # Score = edge * probability (rewards high-prob + high-edge combos)
                ev_score = market_edge * prob
                qualified_bets.append((market, market_edge, kelly, ev_score))

    if qualified_bets:
        # Sort by EV score (edge * prob) instead of pure edge
        qualified_bets.sort(key=lambda x: x[3], reverse=True)
        recommended_bet = qualified_bets[0][0]
        kelly_stake = qualified_bets[0][2]
    else:
        recommended_bet = None
        kelly_stake = 0.0

    if recommended_bet:
        bet_prob = probs[recommended_bet]
        bet_edge = edge[recommended_bet]
        quality_score = bet_edge * kelly_stake * (bet_prob ** 0.5)
        confidence_badge = determine_confidence_badge(bet_edge, bet_prob)
    else:
        quality_score = None
        # Even without a recommended bet, assign a badge based on max prob
        max_prob = max(home_prob, draw_prob, away_prob)
        if max_prob >= 0.85:
            confidence_badge = "ULTRA_SAFE"
        elif max_prob >= 0.75:
            confidence_badge = "HIGH_SAFE"
        elif max_prob >= 0.60:
            confidence_badge = "SAFE"
        elif max_prob >= 0.50:
            confidence_badge = "VALUE"
        elif max_prob >= 0.35:
            confidence_badge = "RISKY"
        else:
            confidence_badge = "ULTRA_RISKY"

    return recommended_bet, kelly_stake, quality_score, confidence_badge


def _match_odds_to_fixture(fixture, odds_list):
    """Find matching odds entry for a fixture from a list of odds data."""
    home_normalized = normalize_team_name_for_matching(
        fixture.get('home_team') or fixture.get('home')
    )
    away_normalized = normalize_team_name_for_matching(
        fixture.get('away_team') or fixture.get('away')
    )

    for odds in odds_list:
        odds_home = normalize_team_name_for_matching(odds.get('home_team'))
        odds_away = normalize_team_name_for_matching(odds.get('away_team'))
        if odds_home == home_normalized and odds_away == away_normalized:
            return odds

    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    """Main execution: train all leagues, fetch fixtures, generate predictions."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force-train', action='store_true', help='Force re-training even if cache exists')
    parser.add_argument('--today', action='store_true', help="Fetch today's fixtures instead of tomorrow's")
    parser.add_argument('--date', type=str, default=None, help='Fetch fixtures for a specific date (YYYY-MM-DD). Works for past dates too.')
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("GENERATEUR DE PREDICTIONS KICKSTAT — MULTI-LIGUE")
    print("=" * 80)

    # ------------------------------------------------------------------
    # Step 1: Load cached models, train only what's missing
    # ------------------------------------------------------------------
    bundles = {}
    if not args.force_train:
        bundles = load_cached_bundles()
        if bundles:
            print(f"\n[CACHE] Modeles charges depuis le cache ({len(bundles)} ligues):")
            for league, bundle in bundles.items():
                print(f"  - {LEAGUE_DISPLAY_NAMES[league]}: {len(bundle.teams)} equipes")

    missing = [lg for lg in DOMESTIC_LEAGUES if lg not in bundles]
    if args.force_train:
        missing = DOMESTIC_LEAGUES
        bundles = {}

    if missing:
        print(f"\n Entrainement des modeles manquants ({len(missing)} ligues)...")
        for league in missing:
            try:
                bundle = train_league_models(league)
                bundles[league] = bundle
                # Save each league immediately after training (crash-safe)
                save_bundles({league: bundle})
                print(f"\n[OK] {LEAGUE_DISPLAY_NAMES[league]} — {len(bundle.teams)} equipes")
            except Exception as e:
                print(f"\n[ERROR] {league}: {e}")

    if not bundles:
        print("\n[FATAL] Aucun modele entraine. Abandon.")
        return

    # ------------------------------------------------------------------
    # Step 2: Fetch tomorrow's fixtures for all leagues
    # ------------------------------------------------------------------
    # Only fetch leagues for which we have models (domestic) + European
    active_leagues = list(bundles.keys()) + EUROPEAN_COMPETITIONS
    # UEL/UECL fixtures from football-data.org: UEL=403, UECL=Copa Sudamericana wrong ID
    # So only fetch UCL from football-data.org; UEL/UECL come from odds synthesis below
    fdorg_leagues = list(bundles.keys()) + ["champions_league"]
    fixtures = get_fixtures_all_leagues(leagues=fdorg_leagues, today=args.today, date=args.date)

    if not fixtures:
        print("\n[WARNING] Aucun match trouve. Export JSON vide.")
        _export_predictions([])
        return

    # ------------------------------------------------------------------
    # Step 3: Fetch odds for all leagues (including UEL/UECL)
    # ------------------------------------------------------------------
    all_odds = get_odds_all_leagues(leagues=active_leagues)

    # Supplement UEL/UECL fixtures from odds data
    # (football-data.org free tier doesn't cover these competitions)
    from datetime import timezone as _tz
    _now = datetime.now(_tz.utc)
    _cutoff = _now + timedelta(days=2)
    for eu_league in ["europa_league", "conference_league"]:
        if eu_league not in all_odds:
            continue
        existing_pairs = {
            (f.get('home') or f.get('home_team', ''), f.get('away') or f.get('away_team', ''))
            for f in fixtures
        }
        for match_odds in all_odds[eu_league]:
            home_raw = match_odds.get('home_team', '')
            away_raw = match_odds.get('away_team', '')
            commence = match_odds.get('commence_time', '')
            if not home_raw or not away_raw or (home_raw, away_raw) in existing_pairs:
                continue
            # Filter to matches within the next 2 days
            try:
                match_dt = datetime.fromisoformat(commence.replace('Z', '+00:00'))
                if match_dt > _cutoff:
                    continue
            except Exception:
                pass
            # Resolve to canonical model name (e.g. "VfB Stuttgart" → "Stuttgart")
            home = resolve_team_canonical(home_raw, bundles)
            away = resolve_team_canonical(away_raw, bundles)
            fixtures.append({
                'home': home,
                'away': away,
                'kickoff': commence,
                'league_slug': eu_league,
                'league': LEAGUE_DISPLAY_NAMES.get(eu_league, eu_league),
                'fixture_id': match_odds.get('id'),
            })
            print(f"  [UEL/UECL] {home} vs {away}")

    # Flatten all odds into a single list for matching
    flat_odds = []
    for odds_list in all_odds.values():
        flat_odds.extend(odds_list)

    # ------------------------------------------------------------------
    # Step 4: Generate predictions for each fixture
    # ------------------------------------------------------------------
    print(f"\n Generation de {len(fixtures)} prediction(s)...")
    predictions = []

    for fixture in fixtures:
        home_team = fixture.get('home') or fixture.get('home_team')
        away_team = fixture.get('away') or fixture.get('away_team')
        kickoff = fixture.get('kickoff') or fixture.get('date')
        league_slug = fixture.get('league_slug', '')
        league_name = fixture.get('league', LEAGUE_DISPLAY_NAMES.get(league_slug, league_slug))

        if not home_team or not away_team:
            continue

        print(f"\n  {league_name}: {home_team} vs {away_team}")

        # Find matching odds
        odds_entry = _match_odds_to_fixture(fixture, flat_odds)
        if odds_entry:
            print(f"    -> Cotes trouvees")

        # European or domestic?
        is_european = league_slug in EUROPEAN_COMPETITIONS

        if is_european:
            pred = generate_european_prediction(
                home_team, away_team, kickoff, bundles, odds_entry
            )
        else:
            # Find the right bundle
            bundle = bundles.get(league_slug)
            if not bundle:
                # Try to find which bundle knows these teams
                found_league = get_league_for_team(home_team, bundles)
                bundle = bundles.get(found_league) if found_league else None

            if not bundle:
                print(f"    -> [SKIP] Pas de modele pour {league_slug}")
                continue

            pred = generate_domestic_prediction(
                home_team, away_team, kickoff, bundle, odds_entry
            )

        if pred:
            pred['league'] = league_name
            pred['league_slug'] = league_slug
            predictions.append(pred)
            status = "BET" if pred['recommended_bet'] else "SKIP"
            print(f"    -> {status} | {pred['model_probs']}")

    # ------------------------------------------------------------------
    # Step 5: Generate combined bets (combos)
    # ------------------------------------------------------------------
    print(f"\n Generation des paris combines...")
    combos = generate_all_combos(predictions, bundles)

    # ------------------------------------------------------------------
    # Step 6: Export
    # ------------------------------------------------------------------
    _export_predictions(predictions, combos)

    print(f"\n{'='*80}")
    print(f" {len(predictions)} prediction(s) generee(s)")

    # Summary by league
    from collections import Counter
    league_counts = Counter(p['league'] for p in predictions)
    for lg, count in league_counts.most_common():
        bets = sum(1 for p in predictions if p['league'] == lg and p['recommended_bet'])
        print(f"   {lg}: {count} matchs, {bets} paris recommandes")

    print(f"{'='*80}\n")


# ---------------------------------------------------------------------------
# Combined bets (combos / accumulators)
# ---------------------------------------------------------------------------

# Same-match combo templates — computed exactly from DC score matrix.
# Only includes combos where BOTH legs have real odds (h2h + totals market).
# BTTS, DC, DNB legs excluded — no real odds available via The Odds API.
SAME_MATCH_COMBOS = [
    # Only draw+over combos — home/away 1X2 markets are disabled (no alpha found)
    # (combo_id, label, condition_fn on (i, j) scores, min_combined_prob)
    ("away_over15", "2 + Over 1.5",
     lambda i, j: j > i and i + j >= 2, 0.15),
    ("away_over25", "2 + Over 2.5",
     lambda i, j: j > i and i + j >= 3, 0.10),
]


def _combo_confidence_tier(prob: float) -> str:
    """Tiered confidence label based on combined probability.
    ULTRA_SAFE: 85%+  |  HIGH_SAFE: 75-85%  |  SAFE: 60-75%
    VALUE: 50-60%     |  RISKY: <50%
    """
    if prob >= 0.85:
        return "ULTRA_SAFE"
    elif prob >= 0.75:
        return "HIGH_SAFE"
    elif prob >= 0.60:
        return "SAFE"
    elif prob >= 0.50:
        return "VALUE"
    elif prob >= 0.35:
        return "RISKY"
    else:
        return "ULTRA_RISKY"


def compute_same_match_combos(prediction: dict, dc_pred) -> list[dict]:
    """Compute same-match combo probabilities using DC score matrix.

    Uses the exact score probability matrix to compute joint probabilities
    rather than multiplying marginal probs (which ignores correlation).
    """
    if not hasattr(dc_pred, 'score_matrix') or dc_pred.score_matrix is None:
        return []

    matrix = dc_pred.score_matrix
    n = matrix.shape[0]

    combos = []
    for combo_id, label, condition_fn, min_prob in SAME_MATCH_COMBOS:
        # Exact probability from score matrix
        prob = sum(
            matrix[i][j]
            for i in range(n) for j in range(n)
            if condition_fn(i, j)
        )

        if prob < min_prob:
            continue

        # Compute combined odds (if individual market odds exist)
        combined_odds = _estimate_combo_odds(combo_id, prediction)
        if combined_odds is None or combined_odds <= 1.0:
            continue

        # Edge = model prob - implied prob
        implied_prob = 1.0 / combined_odds
        edge = prob - implied_prob

        if edge < 0.03:  # Minimum 3% edge for combos
            continue

        kelly = calculate_kelly_stake(prob, combined_odds, fraction=0.15)  # More conservative for combos
        if kelly < 0.5:
            continue

        # Format label using combo_id → direct template (avoids string replacement bugs)
        _combo_label_tpl = {
            "away_over15": "{away} + Over 1.5",
            "away_over25": "{away} + Over 2.5",
        }
        display_label = _combo_label_tpl.get(combo_id, label).format(
            home=prediction['home_team'], away=prediction['away_team']
        )

        combos.append({
            "type": "same_match",
            "combo_id": combo_id,
            "label": display_label,
            "matches": [{
                "home_team": prediction['home_team'],
                "away_team": prediction['away_team'],
                "league": prediction.get('league', ''),
            }],
            "prob": round(prob, 3),
            "combined_odds": round(combined_odds, 2),
            "edge": round(edge * 100, 1),
            "kelly_stake": round(kelly, 1),
            "confidence": _combo_confidence_tier(prob),
        })

    # Sort by edge * prob (EV score)
    combos.sort(key=lambda c: c['edge'] * c['prob'], reverse=True)
    return combos[:3]  # Top 3 per match


def _estimate_combo_odds(combo_id: str, prediction: dict) -> float | None:
    """Estimate combined odds by multiplying individual market odds.

    This is an approximation — real bookmaker combo odds may differ slightly.
    """
    odds = prediction.get('best_odds', {})

    # Map combo to individual legs (only markets with real odds)
    COMBO_LEGS = {
        "away_over15": [('away', None), ('over15', None)],
        "away_over25": [('away', None), ('over25', None)],
    }

    legs = COMBO_LEGS.get(combo_id, [])
    combined = 1.0
    for market_key, _ in legs:
        market_odds = odds.get(market_key, 0)
        if market_odds <= 1.0:
            return None
        combined *= market_odds

    return combined if combined > 1.0 else None


def generate_cross_match_combos(predictions: list[dict], max_legs: int = 3) -> list[dict]:
    """Generate cross-match combos covering all confidence levels.

    Generates 2-leg and 3-leg combos from all recommended bets, then returns
    the best 2 combos per confidence tier (ULTRA_SAFE / HIGH_SAFE / SAFE /
    VALUE / RISKY / ULTRA_RISKY) so every level is represented.
    """
    bet_preds = [p for p in predictions if p.get('recommended_bet')]
    if len(bet_preds) < 2:
        return []

    bet_preds.sort(key=lambda p: p.get('quality_score') or 0, reverse=True)
    top_bets = bet_preds[:12]

    candidates: list[dict] = []

    for n_legs in [2, 3]:
        if len(top_bets) < n_legs:
            continue

        for combo_preds in combinations(top_bets, n_legs):
            legs = []
            combined_prob = 1.0
            combined_odds = 1.0
            valid = True

            for p in combo_preds:
                market = p['recommended_bet']
                prob = _get_market_prob(p, market)
                if prob is None or prob < 0.25:
                    valid = False
                    break

                market_odds = p['best_odds'].get(market, 0)
                if market_odds <= 1.0:
                    valid = False
                    break

                combined_prob *= prob
                combined_odds *= market_odds
                legs.append({
                    "home_team": p['home_team'],
                    "away_team": p['away_team'],
                    "league":    p.get('league', ''),
                    "market":    market,
                    "prob":      round(prob, 3),
                    "odds":      round(market_odds, 2),
                })

            if not valid:
                continue

            implied_prob = 1.0 / combined_odds if combined_odds > 1.0 else 1.0
            edge = combined_prob - implied_prob
            if edge < 0.01:
                continue

            # Kelly fraction decreases with risk: safer combos bet more
            confidence = _combo_confidence_tier(combined_prob)
            kelly_frac = {
                'ULTRA_SAFE': 0.12, 'HIGH_SAFE': 0.10, 'SAFE': 0.10,
                'VALUE': 0.08, 'RISKY': 0.05, 'ULTRA_RISKY': 0.03,
            }.get(confidence, 0.08)

            kelly = calculate_kelly_stake(combined_prob, combined_odds, fraction=kelly_frac)
            if kelly < 0.2:
                continue

            label_parts = []
            for leg in legs:
                market_label = _market_to_label(leg['market'], leg['home_team'], leg['away_team'])
                label_parts.append(f"{leg['home_team'][:3].upper()}-{leg['away_team'][:3].upper()}: {market_label}")

            candidates.append({
                "type":          "cross_match",
                "combo_id":      f"cross_{n_legs}leg_{'_'.join(l['home_team'][:3].lower() for l in legs)}",
                "label":         " + ".join(label_parts),
                "matches":       legs,
                "n_legs":        n_legs,
                "prob":          round(combined_prob, 4),
                "combined_odds": round(combined_odds, 2),
                "edge":          round(edge * 100, 1),
                "kelly_stake":   round(kelly, 1),
                "confidence":    confidence,
            })

    # Keep top 2 per confidence tier so every level is represented
    by_tier: dict[str, list] = {}
    for c in candidates:
        by_tier.setdefault(c['confidence'], []).append(c)

    result: list[dict] = []
    tier_order = ['ULTRA_SAFE', 'HIGH_SAFE', 'SAFE', 'VALUE', 'RISKY', 'ULTRA_RISKY']
    for tier in tier_order:
        tier_combos = by_tier.get(tier, [])
        tier_combos.sort(key=lambda c: c['edge'] * c['prob'], reverse=True)
        result.extend(tier_combos[:2])

    return result


def _get_market_prob(prediction: dict, market: str) -> float | None:
    """Get model probability for a market from prediction dict."""
    probs = prediction.get('model_probs', {})

    # Direct 1X2
    if market in probs:
        return probs[market]

    # Over/Under
    mapping = {
        'over15': ('over_under_15', 'over_15'),
        'under15': ('over_under_15', 'under_15'),
        'over25': ('over_under', 'over_25'),
        'under25': ('over_under', 'under_25'),
        'over35': ('over_under_35', 'over_35'),
        'under35': ('over_under_35', 'under_35'),
    }
    if market in mapping:
        section, key = mapping[market]
        sec_data = prediction.get(section, {})
        return sec_data.get(key) if sec_data else None

    return None


def _market_to_label(market: str, home: str, away: str) -> str:
    """Convert market key to human-readable label."""
    labels = {
        'home': home, 'draw': 'Nul', 'away': away,
        'over15': 'O1.5', 'under15': 'U1.5',
        'over25': 'O2.5', 'under25': 'U2.5',
        'over35': 'O3.5', 'under35': 'U3.5',
        'spread_home_m15': f'{home} -1.5', 'spread_away_p15': f'{away} +1.5',
        'spread_home_m25': f'{home} -2.5', 'spread_away_p25': f'{away} +2.5',
    }
    return labels.get(market, market)


def generate_all_combos(predictions: list[dict], bundles: dict) -> list[dict]:
    """Generate all combo recommendations: same-match + cross-match."""
    all_combos = []

    # Same-match combos (using DC score matrix for exact probs)
    for pred in predictions:
        home_team = pred['home_team']
        away_team = pred['away_team']
        league_slug = pred.get('league_slug', '')

        # Get DC prediction for score matrix
        dc_pred = None
        if league_slug in bundles:
            try:
                dc_pred = bundles[league_slug].dc_model.predict(home_team, away_team)
            except Exception:
                pass
        elif not pred.get('is_european', False):
            # Try to find bundle
            found_league = get_league_for_team(home_team, bundles)
            if found_league and found_league in bundles:
                try:
                    dc_pred = bundles[found_league].dc_model.predict(home_team, away_team)
                except Exception:
                    pass

        if dc_pred:
            same_combos = compute_same_match_combos(pred, dc_pred)
            all_combos.extend(same_combos)

    # Cross-match combos
    cross_combos = generate_cross_match_combos(predictions)
    all_combos.extend(cross_combos)

    # Sort everything by edge * prob
    all_combos.sort(key=lambda c: c['edge'] * c['prob'], reverse=True)

    print(f"\n[OK] {len(all_combos)} combo(s) genere(s)")
    for c in all_combos[:5]:
        print(f"  - {c['label']} | Cote: {c['combined_odds']} | Prob: {c['prob']:.1%} | Edge: {c['edge']}%")

    return all_combos


def _export_predictions(predictions: list[dict], combos: list[dict] | None = None):
    """Write predictions to JSON file."""
    output_path = PROJECT_ROOT / "web" / "public" / "predictions.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "predictions": predictions,
        "combos": combos or [],
        "generated_at": datetime.now().isoformat(),
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Predictions exportees vers: {output_path}")


if __name__ == "__main__":
    main()
