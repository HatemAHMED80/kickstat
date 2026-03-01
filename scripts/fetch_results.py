#!/usr/bin/env python3
"""
fetch_results.py — Fetch match results and update history.json

Run this script after matches have finished (e.g. via daily_predictions.ps1).
Reads past predictions from web/public/predictions.json,
matches them against football-data.co.uk CSV results,
and writes W/L outcomes to data/results/history.json + web/public/history.json.

Usage:
    python scripts/fetch_results.py
"""
import csv
import io
import json
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import httpx
from loguru import logger

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
PREDICTIONS_FILE = PROJECT_ROOT / "web" / "public" / "predictions.json"
HISTORY_FILE = PROJECT_ROOT / "data" / "results" / "history.json"
PUBLIC_HISTORY_FILE = PROJECT_ROOT / "web" / "public" / "history.json"

# ---------------------------------------------------------------------------
# League → football-data.co.uk code mapping
# ---------------------------------------------------------------------------
LEAGUE_CODE_MAP = {
    "Premier League": "E0",
    "Ligue 1": "F1",
    "La Liga": "SP1",
    "Bundesliga": "D1",
    "Serie A": "I1",
}


def _season_suffix(date_str: str) -> str:
    """Return season code like '2526' from an ISO date string."""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    year = dt.year
    month = dt.month
    # Season starts in July/August
    if month >= 7:
        return f"{str(year)[2:]}{str(year + 1)[2:]}"
    return f"{str(year - 1)[2:]}{str(year)[2:]}"


def _download_csv(league_code: str, season: str) -> list[dict]:
    """Download and parse a football-data.co.uk CSV file."""
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"
    logger.info(f"Downloading {url}")
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        # Only keep rows with full-time results
        return [row for row in reader if row.get("FTHG") and row.get("FTAG")]
    except Exception as exc:
        logger.warning(f"Failed to fetch {league_code}/{season}: {exc}")
        return []


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_match(rows: list[dict], home_team: str, away_team: str, date_str: str) -> dict | None:
    """Find the best-matching row in a CSV for a given match."""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    target_date = dt.date()

    best_row = None
    best_score = 0.0

    for row in rows:
        # Parse date (DD/MM/YYYY or DD/MM/YY)
        raw_date = row.get("Date", "")
        try:
            parts = raw_date.split("/")
            if len(parts) == 3:
                d, m, y = parts
                if len(y) == 2:
                    y = "20" + y
                row_date = datetime(int(y), int(m), int(d)).date()
                # Allow ±2 days for timezone/postponed-match tolerance
                if abs((row_date - target_date).days) > 2:
                    continue
        except Exception:
            continue

        home_sim = _similarity(home_team, row.get("HomeTeam", ""))
        away_sim = _similarity(away_team, row.get("AwayTeam", ""))
        score = (home_sim + away_sim) / 2

        if score > best_score:
            best_score = score
            best_row = row

    if best_score >= 0.60 and best_row:
        return best_row
    return None


def _resolve_bet(bet: str, home_score: int, away_score: int, odds: float) -> tuple[bool | None, float]:
    """Determine if a bet won (None = push). Returns (won, pnl).

    pnl is profit/loss on a 1-unit stake:
      won  → odds − 1
      lost → −1
      push → 0
    """
    total = home_score + away_score
    diff = home_score - away_score

    won: bool | None
    match bet:
        case "home":
            won = diff > 0
        case "draw":
            won = diff == 0
        case "away":
            won = diff < 0
        case "over15":
            won = total >= 2
        case "under15":
            won = total <= 1
        case "over25":
            won = total >= 3
        case "under25":
            won = total <= 2
        case "over35":
            won = total >= 4
        case "under35":
            won = total <= 3
        case "dc_1x":
            won = diff >= 0
        case "dc_x2":
            won = diff <= 0
        case "dc_12":
            won = diff != 0
        case "dnb_home":
            won = True if diff > 0 else (None if diff == 0 else False)
        case "dnb_away":
            won = True if diff < 0 else (None if diff == 0 else False)
        case "spread_home_m15":
            won = diff >= 2
        case "spread_away_p15":
            won = diff <= 1   # away wins, draw, or home by 1
        case "spread_home_m25":
            won = diff >= 3
        case "spread_away_p25":
            won = diff <= 2
        case "ah_home":
            # Default -1.5 line: home must win by 2+
            won = diff >= 2
        case "ah_away":
            # Default +1.5 line: away covers if home doesn't win by 2+
            won = diff <= 1
        case _:
            return None, 0.0

    if won is None:
        pnl = 0.0
    elif won:
        pnl = round(odds - 1.0, 4)
    else:
        pnl = -1.0

    return won, pnl


def main() -> None:
    # ------------------------------------------------------------------
    # Load predictions
    # ------------------------------------------------------------------
    if not PREDICTIONS_FILE.exists():
        logger.error(f"Predictions file not found: {PREDICTIONS_FILE}")
        return

    with open(PREDICTIONS_FILE, encoding="utf-8") as f:
        raw = json.load(f)

    predictions: list[dict] = raw.get("predictions", raw) if isinstance(raw, dict) else raw

    # ------------------------------------------------------------------
    # Load existing history
    # ------------------------------------------------------------------
    history: list[dict] = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

    existing_ids = {h["id"] for h in history}

    # ------------------------------------------------------------------
    # Find past predictions not yet recorded
    # ------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    to_resolve = [
        p for p in predictions
        if p.get("recommended_bet")
        and datetime.fromisoformat(p["kickoff"].replace("Z", "+00:00")) < now
        and p["match_id"] not in existing_ids
    ]

    if not to_resolve:
        logger.info("No new past predictions to resolve.")
    else:
        logger.info(f"Resolving {len(to_resolve)} past prediction(s)...")

    # ------------------------------------------------------------------
    # Fetch results (cache CSV per league+season)
    # ------------------------------------------------------------------
    csv_cache: dict[str, list[dict]] = {}

    for pred in to_resolve:
        league = pred.get("league", "")
        kickoff = pred.get("kickoff", "")
        home_team = pred.get("home_team", "")
        away_team = pred.get("away_team", "")
        recommended_bet = pred.get("recommended_bet", "")
        match_id = pred.get("match_id", "")

        league_code = LEAGUE_CODE_MAP.get(league)
        if not league_code:
            logger.warning(f"Unknown league '{league}' — skipping {home_team} vs {away_team}")
            continue

        season = _season_suffix(kickoff)
        cache_key = f"{league_code}_{season}"

        if cache_key not in csv_cache:
            csv_cache[cache_key] = _download_csv(league_code, season)

        rows = csv_cache[cache_key]
        row = _find_match(rows, home_team, away_team, kickoff)

        base_record: dict = {
            "id": match_id,
            "date": kickoff[:10],
            "kickoff": kickoff,
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "recommended_bet": recommended_bet,
            "odds": pred.get("best_odds", {}).get(recommended_bet),
            "model_prob": pred.get("model_probs", {}).get(recommended_bet),
            "edge_pct": pred.get("edge", {}).get(recommended_bet),
            "confidence_badge": pred.get("confidence_badge"),
        }

        if not row:
            logger.warning(f"No CSV result found for {home_team} vs {away_team} ({kickoff[:10]})")
            history.append({**base_record, "resolved": False})
            continue

        try:
            home_score = int(row["FTHG"])
            away_score = int(row["FTAG"])
        except (KeyError, ValueError):
            logger.warning(f"Invalid score data for {home_team} vs {away_team}")
            history.append({**base_record, "resolved": False})
            continue

        odds = base_record["odds"] or 2.0
        won, pnl = _resolve_bet(recommended_bet, home_score, away_score, odds)

        status = "WIN" if won is True else ("PUSH" if won is None else "LOSS")
        logger.info(
            f"  {home_team} {home_score}–{away_score} {away_team} | "
            f"{recommended_bet} | {status} | pnl={pnl:+.2f}"
        )

        history.append({
            **base_record,
            "home_score": home_score,
            "away_score": away_score,
            "won": won,
            "pnl": pnl,
            "resolved": True,
        })

    # ------------------------------------------------------------------
    # Sort chronologically and save
    # ------------------------------------------------------------------
    history.sort(key=lambda x: x.get("date", ""))

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    PUBLIC_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PUBLIC_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    resolved = [h for h in history if h.get("resolved")]
    if resolved:
        wins = sum(1 for h in resolved if h.get("won") is True)
        losses = sum(1 for h in resolved if h.get("won") is False)
        total_pnl = sum(h.get("pnl", 0) for h in resolved)
        win_rate = wins / len(resolved) * 100 if resolved else 0
        roi = total_pnl / len(resolved) * 100 if resolved else 0
        logger.info(
            f"\nRésumé : {len(resolved)} paris | {wins}V {losses}D | "
            f"Taux de réussite : {win_rate:.1f}% | ROI : {roi:+.1f}%"
        )

    logger.info(f"Historique sauvegardé : {len(history)} entrées")
    logger.info(f"  → {HISTORY_FILE}")
    logger.info(f"  → {PUBLIC_HISTORY_FILE}")


if __name__ == "__main__":
    main()
