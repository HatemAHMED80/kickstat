"""Football-Data.co.uk CSV downloader and parser.

Free historical match results + betting odds for 20+ leagues since 2000.
Data source: https://www.football-data.co.uk/data.php

This is the gold standard for backtesting betting models:
- Pinnacle closing odds (sharpest line in the market)
- Market max odds (best available to bet)
- Results + stats in the same file
"""

import io
from pathlib import Path

import httpx
import pandas as pd
from loguru import logger


# Match statistics columns available in football-data.co.uk CSVs
STAT_COLS = ["HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"]

# League codes for football-data.co.uk CSV URLs
LEAGUE_CODES = {
    # Top 5 leagues
    "ligue_1": "F1",
    "premier_league": "E0",
    "la_liga": "SP1",
    "bundesliga": "D1",
    "serie_a": "I1",
    # Secondary leagues (less efficient pricing)
    "ligue_2": "F2",
    "championship": "E1",
    "league_one": "E2",
    "league_two": "E3",
    "bundesliga_2": "D2",
    "serie_b": "I2",
    "la_liga_2": "SP2",
    "super_lig": "T1",
    "super_league_greece": "G1",
    "eredivisie": "N1",
    "jupiler_league": "B1",
    "primeira_liga": "P1",
    "scottish_prem": "SC0",
    "scottish_champ": "SC1",
}

# Season format: "2324" for 2023-24
def _season_code(start_year: int) -> str:
    """Convert season start year to football-data.co.uk format."""
    end = (start_year + 1) % 100
    return f"{start_year % 100:02d}{end:02d}"


def download_season_csv(
    league: str = "ligue_1",
    season: int = 2024,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Download a single season CSV from football-data.co.uk.

    Args:
        league: League key from LEAGUE_CODES.
        season: Season start year (2024 = 2024-25).
        cache_dir: If provided, cache CSV locally.

    Returns:
        DataFrame with match results and odds.
    """
    code = LEAGUE_CODES.get(league, league)
    sc = _season_code(season)
    url = f"https://www.football-data.co.uk/mmz4281/{sc}/{code}.csv"

    # Check cache first
    if cache_dir:
        cache_path = cache_dir / f"{code}_{sc}.csv"
        if cache_path.exists():
            logger.info(f"Loading cached {cache_path}")
            return pd.read_csv(cache_path)

    logger.info(f"Downloading {url}")
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text))

    # Cache if requested
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
        logger.info(f"Cached to {cache_path}")

    return df


def parse_season(df: pd.DataFrame, season: int) -> list[dict]:
    """Parse a football-data.co.uk DataFrame into match + odds dicts.

    Returns list of dicts with keys:
        home_team, away_team, home_score, away_score, kickoff,
        pinnacle_home, pinnacle_draw, pinnacle_away,
        max_home, max_draw, max_away,
        avg_home, avg_draw, avg_away,
        b365_home, b365_draw, b365_away,
        max_over25, max_under25
    """
    matches = []

    for _, row in df.iterrows():
        # Skip rows without results
        if pd.isna(row.get("FTHG")) or pd.isna(row.get("FTAG")):
            continue

        # Parse date (dd/mm/yyyy or dd/mm/yy)
        date_str = str(row.get("Date", ""))
        try:
            kickoff = pd.to_datetime(date_str, dayfirst=True)
        except (ValueError, TypeError):
            continue

        home = str(row.get("HomeTeam", "")).strip()
        away = str(row.get("AwayTeam", "")).strip()
        if not home or not away:
            continue

        match = {
            "home_team": home,
            "away_team": away,
            "home_score": int(row["FTHG"]),
            "away_score": int(row["FTAG"]),
            "kickoff": kickoff,
            "season": season,
        }

        # Match statistics (shots, corners, fouls, cards)
        for col in STAT_COLS:
            val = row.get(col)
            match[col.lower()] = int(val) if pd.notna(val) else 0

        # Half-time scores
        match["hthg"] = int(row["HTHG"]) if pd.notna(row.get("HTHG")) else 0
        match["htag"] = int(row["HTAG"]) if pd.notna(row.get("HTAG")) else 0

        # Pinnacle odds (PSH/PSD/PSA in newer files, PH/PD/PA in older)
        match["pinnacle_home"] = _get_odds(row, "PSH", "PH")
        match["pinnacle_draw"] = _get_odds(row, "PSD", "PD")
        match["pinnacle_away"] = _get_odds(row, "PSA", "PA")

        # Market max odds (best available)
        match["max_home"] = _get_odds(row, "MaxH", "BbMxH")
        match["max_draw"] = _get_odds(row, "MaxD", "BbMxD")
        match["max_away"] = _get_odds(row, "MaxA", "BbMxA")

        # Market average
        match["avg_home"] = _get_odds(row, "AvgH", "BbAvH")
        match["avg_draw"] = _get_odds(row, "AvgD", "BbAvD")
        match["avg_away"] = _get_odds(row, "AvgA", "BbAvA")

        # Bet365
        match["b365_home"] = _get_odds(row, "B365H")
        match["b365_draw"] = _get_odds(row, "B365D")
        match["b365_away"] = _get_odds(row, "B365A")

        # Over/Under 2.5 goals
        match["pinnacle_over25"] = _get_odds(row, "P>2.5")
        match["pinnacle_under25"] = _get_odds(row, "P<2.5")
        match["max_over25"] = _get_odds(row, "Max>2.5", "BbMx>2.5")
        match["max_under25"] = _get_odds(row, "Max<2.5", "BbMx<2.5")
        match["avg_over25"] = _get_odds(row, "Avg>2.5", "BbAv>2.5")
        match["avg_under25"] = _get_odds(row, "Avg<2.5", "BbAv<2.5")

        # Corner 1X2 (home more / equal / away more corners)
        match["pinnacle_corner_home"] = _get_odds(row, "PSCH")
        match["pinnacle_corner_draw"] = _get_odds(row, "PSCD")
        match["pinnacle_corner_away"] = _get_odds(row, "PSCA")
        match["max_corner_home"] = _get_odds(row, "MaxCH")
        match["max_corner_draw"] = _get_odds(row, "MaxCD")
        match["max_corner_away"] = _get_odds(row, "MaxCA")

        # Corner Over/Under 2.5 (total corners)
        match["pinnacle_corner_over"] = _get_odds(row, "PC>2.5")
        match["pinnacle_corner_under"] = _get_odds(row, "PC<2.5")
        match["max_corner_over"] = _get_odds(row, "MaxC>2.5")
        match["max_corner_under"] = _get_odds(row, "MaxC<2.5")

        # Asian Handicap (goals)
        match["ah_line"] = _get_odds(row, "AHh")
        match["pinnacle_ahh"] = _get_odds(row, "PAHH")
        match["pinnacle_aha"] = _get_odds(row, "PAHA")
        match["max_ahh"] = _get_odds(row, "MaxAHH")
        match["max_aha"] = _get_odds(row, "MaxAHA")

        matches.append(match)

    logger.info(f"Parsed {len(matches)} matches for {season}-{season+1}")
    return matches


def _get_odds(row: pd.Series, *col_names: str) -> float:
    """Get odds from first available column."""
    for col in col_names:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
    return 0.0


def load_historical_data(
    league: str = "ligue_1",
    seasons: list[int] | None = None,
    cache_dir: Path | None = None,
) -> list[dict]:
    """Load multiple seasons of historical data with odds.

    Args:
        league: League key.
        seasons: List of season start years. Default: 2020-2024.
        cache_dir: Where to cache downloaded CSVs.

    Returns:
        Combined list of match dicts sorted by kickoff date.
    """
    if seasons is None:
        seasons = [2020, 2021, 2022, 2023, 2024]

    all_matches = []
    for season in seasons:
        try:
            df = download_season_csv(league, season, cache_dir)
            matches = parse_season(df, season)
            all_matches.extend(matches)
        except Exception as e:
            logger.warning(f"Failed to load {league} {season}: {e}")

    # Sort chronologically
    all_matches.sort(key=lambda m: m["kickoff"])
    logger.info(f"Total: {len(all_matches)} matches across {len(seasons)} seasons")
    return all_matches


def build_odds_lookup(matches: list[dict], odds_source: str = "pinnacle") -> dict:
    """Build odds lookup dict for the backtest engine.

    Args:
        matches: List of match dicts from parse_season().
        odds_source: Which odds to use for fair value calculation.
            "pinnacle" = Pinnacle closing (sharpest)
            "avg" = Market average
            "b365" = Bet365

    Returns:
        Dict mapping match_key to odds dict.
    """
    prefix_map = {
        "pinnacle": ("pinnacle_home", "pinnacle_draw", "pinnacle_away"),
        "avg": ("avg_home", "avg_draw", "avg_away"),
        "b365": ("b365_home", "b365_draw", "b365_away"),
    }
    h_col, d_col, a_col = prefix_map.get(odds_source, prefix_map["pinnacle"])

    odds_data = {}
    for m in matches:
        # Include date to avoid collisions across seasons
        date_str = str(m["kickoff"])[:10]  # YYYY-MM-DD
        key = f"{m['home_team']}_vs_{m['away_team']}_{date_str}"
        h, d, a = m.get(h_col, 0), m.get(d_col, 0), m.get(a_col, 0)
        if h > 1.0 and d > 1.0 and a > 1.0:
            odds_data[key] = {
                "home_odds": h,
                "draw_odds": d,
                "away_odds": a,
                # Best available odds for PnL (always use max)
                "best_home": m.get("max_home", h),
                "best_draw": m.get("max_draw", d),
                "best_away": m.get("max_away", a),
            }
    logger.info(f"Built odds lookup: {len(odds_data)} matches with valid odds")
    return odds_data


def build_multi_market_odds(matches: list[dict]) -> dict:
    """Build odds lookup for ALL markets (1X2, O/U goals, corner 1X2, corner O/U).

    Uses Pinnacle for fair value, Max for best available PnL.

    Returns:
        Dict mapping match_key to dict of market odds.
    """
    odds_data = {}
    for m in matches:
        date_str = str(m["kickoff"])[:10]
        key = f"{m['home_team']}_vs_{m['away_team']}_{date_str}"

        entry = {}

        # 1X2 match odds (Pinnacle fair value, Max for PnL)
        ph, pd_, pa = m.get("pinnacle_home", 0), m.get("pinnacle_draw", 0), m.get("pinnacle_away", 0)
        if ph > 1.0 and pd_ > 1.0 and pa > 1.0:
            entry["1x2"] = {
                "pin_home": ph, "pin_draw": pd_, "pin_away": pa,
                "best_home": m.get("max_home", ph),
                "best_draw": m.get("max_draw", pd_),
                "best_away": m.get("max_away", pa),
            }

        # Over/Under 2.5 goals
        po, pu = m.get("pinnacle_over25", 0), m.get("pinnacle_under25", 0)
        if po > 1.0 and pu > 1.0:
            entry["ou25"] = {
                "pin_over": po, "pin_under": pu,
                "best_over": m.get("max_over25", po),
                "best_under": m.get("max_under25", pu),
            }

        # Corner 1X2 (home more / equal / away more)
        pch = m.get("pinnacle_corner_home", 0)
        pcd = m.get("pinnacle_corner_draw", 0)
        pca = m.get("pinnacle_corner_away", 0)
        if pch > 1.0 and pcd > 1.0 and pca > 1.0:
            entry["corner_1x2"] = {
                "pin_home": pch, "pin_draw": pcd, "pin_away": pca,
                "best_home": m.get("max_corner_home", pch),
                "best_draw": m.get("max_corner_draw", pcd),
                "best_away": m.get("max_corner_away", pca),
            }

        # Corner Over/Under
        pco = m.get("pinnacle_corner_over", 0)
        pcu = m.get("pinnacle_corner_under", 0)
        if pco > 1.0 and pcu > 1.0:
            entry["corner_ou"] = {
                "pin_over": pco, "pin_under": pcu,
                "best_over": m.get("max_corner_over", pco),
                "best_under": m.get("max_corner_under", pcu),
            }

        if entry:
            odds_data[key] = entry

    # Count market coverage
    n = len(odds_data)
    for mkt in ["1x2", "ou25", "corner_1x2", "corner_ou"]:
        count = sum(1 for v in odds_data.values() if mkt in v)
        logger.info(f"  {mkt}: {count}/{n} matches with odds")

    return odds_data
