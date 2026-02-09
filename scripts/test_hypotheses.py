#!/usr/bin/env python3
"""Rapid hypothesis testing to find edges against bookmakers.

Tests multiple hypotheses on a single league (fast iteration).
If something works, we validate on the full dataset.

Hypotheses:
  H1: Form-weighted ELO (K=64 for last 5 matches)
  H2: Home/away ELO split (separate ratings)
  H3: Closing Line Value (do we predict line movement?)
  H4: Early season mispricing (matchday 1-6)
  H5: Shorter DC half-life (90 days vs 180)
  H6: Promoted teams mispricing
  H7: Asian Handicap edges
  H8: Favorite-longshot bias (underdogs overpriced?)
  H9: Model agreement filter (DC+ELO agree → stronger signal)
  H10: BTTS and alternative O/U lines (1.5, 3.5)
"""

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data, STAT_COLS
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.prop_models import remove_margin_2way, remove_margin_3way


def build_match_results(matches):
    return [
        MatchResult(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
            date=m["kickoff"],
        )
        for m in matches
    ]


def roi_stats(bets):
    """Calculate ROI stats from list of (won, odds) tuples."""
    if not bets:
        return {"n": 0, "roi": 0, "pnl": 0, "win_rate": 0}
    n = len(bets)
    wins = sum(1 for w, _ in bets if w)
    pnl = sum((o - 1.0) if w else -1.0 for w, o in bets)
    return {
        "n": n,
        "roi": round(pnl / n * 100, 1),
        "pnl": round(pnl, 1),
        "win_rate": round(wins / n * 100, 1),
    }


def print_result(label, stats):
    if stats["n"] == 0:
        print(f"  {label:<55} NO BETS")
        return
    marker = " <<<" if stats["roi"] > 0 else ""
    print(f"  {label:<55} {stats['n']:>5} bets | "
          f"win {stats['win_rate']:>5.1f}% | "
          f"ROI {stats['roi']:>+6.1f}% | "
          f"PnL {stats['pnl']:>+7.1f}u{marker}")


def run_all_hypotheses(league="ligue_1", seasons=None):
    if seasons is None:
        seasons = [2020, 2021, 2022, 2023, 2024]

    cache_dir = PROJECT_ROOT / "data" / "historical"
    matches = load_historical_data(league, seasons, cache_dir)
    matches = sorted(matches, key=lambda m: m["kickoff"])
    n = len(matches)
    print(f"\n{'='*75}")
    print(f"  HYPOTHESIS TESTING - {league.upper()} ({n} matches, seasons {seasons[0]}-{seasons[-1]})")
    print(f"{'='*75}")

    min_train = 100
    refit = 120  # fewer DC refits for speed

    # === Setup models ===
    elo_std = EloRating(k_factor=32, home_advantage=100)
    elo_form = EloRating(k_factor=64, home_advantage=100)  # H1: higher K
    elo_home = {}  # H2: home/away split - {team: {home_elo, away_elo}}
    dc = None
    dc_short = None  # H5: shorter half-life

    # Track matchday per season
    season_matchdays = defaultdict(int)
    season_match_count = defaultdict(int)

    # Initialize models on training window
    for m in matches[:min_train]:
        em = EloMatch(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
        )
        elo_std.update(em)
        elo_form.update(em)
        _update_home_away_elo(elo_home, m)

    # Collect bets per hypothesis
    H = {f"H{i}": [] for i in range(1, 11)}
    H["baseline"] = []
    H["baseline_with_edge"] = []  # (won, odds, edge) for threshold analysis
    H["H7_lines"] = defaultdict(list)  # per AH line
    H["H10_ou15"] = []
    H["H10_ou35"] = []
    H["H10_btts"] = []
    # H3: CLV tracking
    h3_clv = {"correct": 0, "total": 0, "magnitude": []}

    for i in range(min_train, n):
        test = matches[i]

        # Update models with previous match
        if i > min_train:
            prev = matches[i - 1]
            em = EloMatch(
                home_team=prev["home_team"], away_team=prev["away_team"],
                home_goals=prev["home_score"], away_goals=prev["away_score"],
            )
            elo_std.update(em)
            elo_form.update(em)
            _update_home_away_elo(elo_home, prev)

        # Refit DC
        if dc is None or (i - min_train) % refit == 0:
            dc_train = build_match_results(matches[:i])
            dc = DixonColesModel(half_life_days=180)
            dc_short = DixonColesModel(half_life_days=90)  # H5
            try:
                dc.fit(dc_train)
                dc_short.fit(dc_train)
            except ValueError:
                continue

        # Predictions
        dc_pred = dc.predict(test["home_team"], test["away_team"])
        dc_short_pred = dc_short.predict(test["home_team"], test["away_team"])
        elo_probs = elo_std.predict_1x2(test["home_team"], test["away_team"])
        elo_form_probs = elo_form.predict_1x2(test["home_team"], test["away_team"])
        ha_elo_probs = _predict_home_away_elo(elo_home, test["home_team"], test["away_team"])

        # Ensemble: DC 0.65 + ELO 0.35
        ens = _ensemble(dc_pred, elo_probs, 0.65, 0.35)

        # Actual outcome
        hs, aws = test["home_score"], test["away_score"]
        outcome_1x2 = 0 if hs > aws else (1 if hs == aws else 2)

        # Opening odds (PSH/PSD/PSA)
        pin_h = test.get("pinnacle_home", 0)
        pin_d = test.get("pinnacle_draw", 0)
        pin_a = test.get("pinnacle_away", 0)
        if not (pin_h > 1.0 and pin_d > 1.0 and pin_a > 1.0):
            continue

        max_h = test.get("max_home", pin_h)
        max_d = test.get("max_draw", pin_d)
        max_a = test.get("max_away", pin_a)

        fair_h, fair_d, fair_a = remove_margin_3way(pin_h, pin_d, pin_a)

        # Track matchday for H4
        season = test.get("season", 0)
        season_match_count[season] += 1
        # Approximate matchday (20 teams = 10 matches per matchday)
        matchday = season_match_count[season] // 10 + 1

        # ─── BASELINE: Standard ensemble, 5% edge ───
        _check_1x2_edge(H["baseline"], ens, fair_h, fair_d, fair_a,
                        max_h, max_d, max_a, outcome_1x2, min_edge=5.0)
        # Also store with edge for threshold analysis (min_edge=0)
        _check_1x2_edge_with_data(H["baseline_with_edge"], ens, fair_h, fair_d, fair_a,
                                   max_h, max_d, max_a, outcome_1x2, min_edge=0.0)

        # ─── H1: Form ELO (K=64) instead of standard ───
        ens_form = _ensemble(dc_pred, elo_form_probs, 0.65, 0.35)
        _check_1x2_edge(H["H1"], ens_form, fair_h, fair_d, fair_a,
                        max_h, max_d, max_a, outcome_1x2, min_edge=5.0)

        # ─── H2: Home/Away ELO split ───
        ens_ha = _ensemble(dc_pred, ha_elo_probs, 0.65, 0.35)
        _check_1x2_edge(H["H2"], ens_ha, fair_h, fair_d, fair_a,
                        max_h, max_d, max_a, outcome_1x2, min_edge=5.0)

        # ─── H3: Closing Line Value ───
        # Do we predict the direction the line moves?
        closing_h = test.get("pinnacle_home", 0)
        # We used opening odds as pinnacle_home. But wait -
        # in our data, PSH = opening, PSCH = closing
        # We need to check if closing odds are different from opening
        # Unfortunately, our parser mapped PSCH as "pinnacle_corner_home"
        # which is actually closing 1X2. Let's use that!
        closing_h_actual = test.get("pinnacle_corner_home", 0)  # actually PSCH = closing home
        closing_d_actual = test.get("pinnacle_corner_draw", 0)  # actually PSCD = closing draw
        closing_a_actual = test.get("pinnacle_corner_away", 0)  # actually PSCA = closing away
        if closing_h_actual > 1.0 and pin_h > 1.0:
            # Opening implied prob
            open_prob_h = 1 / pin_h
            close_prob_h = 1 / closing_h_actual
            model_prob_h = ens["home"]
            # Model says home is more likely than opening implies
            model_says_higher = model_prob_h > open_prob_h
            # Line moved towards higher (closing prob > opening prob)
            line_moved_higher = close_prob_h > open_prob_h
            if model_says_higher == line_moved_higher and abs(close_prob_h - open_prob_h) > 0.01:
                h3_clv["correct"] += 1
            if abs(close_prob_h - open_prob_h) > 0.01:
                h3_clv["total"] += 1
                h3_clv["magnitude"].append(abs(close_prob_h - open_prob_h))

        # Also test: bet using OPENING odds, settle at closing fair value
        fair_ch, fair_cd, fair_ca = (0, 0, 0)
        if closing_h_actual > 1.0 and closing_d_actual > 1.0 and closing_a_actual > 1.0:
            fair_ch, fair_cd, fair_ca = remove_margin_3way(
                closing_h_actual, closing_d_actual, closing_a_actual
            )
            # Edge vs CLOSING odds (harder benchmark)
            _check_1x2_edge(H["H3"], ens, fair_ch, fair_cd, fair_ca,
                            max_h, max_d, max_a, outcome_1x2, min_edge=5.0)

        # ─── H4: Early season (matchday <= 6) ───
        if matchday <= 6:
            _check_1x2_edge(H["H4"], ens, fair_h, fair_d, fair_a,
                            max_h, max_d, max_a, outcome_1x2, min_edge=3.0)

        # ─── H5: Shorter DC half-life (90 days) ───
        ens_short = _ensemble(dc_short_pred, elo_probs, 0.65, 0.35)
        _check_1x2_edge(H["H5"], ens_short, fair_h, fair_d, fair_a,
                        max_h, max_d, max_a, outcome_1x2, min_edge=5.0)

        # ─── H6: Promoted teams ───
        # Simple proxy: team has fewer than 40 matches in training data
        home_matches = sum(1 for m in matches[:i]
                          if m["home_team"] == test["home_team"] or m["away_team"] == test["home_team"])
        away_matches = sum(1 for m in matches[:i]
                          if m["home_team"] == test["away_team"] or m["away_team"] == test["away_team"])
        if home_matches < 40 or away_matches < 40:
            _check_1x2_edge(H["H6"], ens, fair_h, fair_d, fair_a,
                            max_h, max_d, max_a, outcome_1x2, min_edge=3.0)

        # ─── H7: Asian Handicap ───
        ah_line = test.get("ah_line", 0)
        pin_ahh = test.get("pinnacle_ahh", 0)
        pin_aha = test.get("pinnacle_aha", 0)
        max_ahh = test.get("max_ahh", pin_ahh)
        max_aha = test.get("max_aha", pin_aha)
        if ah_line != 0 and pin_ahh > 1.0 and pin_aha > 1.0:
            # Calculate model prob of covering the handicap
            goal_diff = hs - aws
            # Home covers if goal_diff > -ah_line (ah_line is usually negative for favorites)
            model_cover_home = _prob_cover_ah(dc_pred.score_matrix, ah_line)
            model_cover_away = 1.0 - model_cover_home

            fair_ahh, fair_aha = remove_margin_2way(pin_ahh, pin_aha)

            for label, model_p, fair_p, best_o, won in [
                ("ah_home", model_cover_home, fair_ahh, max_ahh,
                 _ah_won(goal_diff, ah_line, "home")),
                ("ah_away", model_cover_away, fair_aha, max_aha,
                 _ah_won(goal_diff, ah_line, "away")),
            ]:
                if fair_p <= 0 or best_o <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= 5.0:
                    H["H7"].append((won, best_o))
                    H["H7_lines"][ah_line].append((won, best_o, edge))

        # ─── H8: Favorite-longshot bias ───
        # Test: are big underdogs (odds > 4.0) profitable?
        for _, model_p, fair_p, best_o, win_idx in [
            ("home", ens["home"], fair_h, max_h, 0),
            ("draw", ens["draw"], fair_d, max_d, 1),
            ("away", ens["away"], fair_a, max_a, 2),
        ]:
            if best_o > 4.0 and fair_p > 0:
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= 3.0:
                    won = outcome_1x2 == win_idx
                    H["H8"].append((won, best_o))

        # ─── H9: Model agreement filter ───
        # When DC and ELO agree strongly AND differ from market
        dc_probs = [dc_pred.home_win, dc_pred.draw, dc_pred.away_win]
        elo_arr = [elo_probs["home"], elo_probs["draw"], elo_probs["away"]]
        disagreement = sum(abs(a - b) for a, b in zip(dc_probs, elo_arr))
        if disagreement < 0.10:  # Models strongly agree
            _check_1x2_edge(H["H9"], ens, fair_h, fair_d, fair_a,
                            max_h, max_d, max_a, outcome_1x2, min_edge=5.0)

        # ─── H10: BTTS + alternative O/U lines ───
        pin_o25 = test.get("pinnacle_over25", 0)
        pin_u25 = test.get("pinnacle_under25", 0)
        max_o25 = test.get("max_over25", pin_o25)
        max_u25 = test.get("max_under25", pin_u25)
        total_goals = hs + aws

        if pin_o25 > 1.0 and pin_u25 > 1.0:
            fair_over, fair_under = remove_margin_2way(pin_o25, pin_u25)

            # O/U 2.5 from score matrix (more accurate than lambda-based)
            model_o25 = float(sum(
                dc_pred.score_matrix[i, j]
                for i in range(9) for j in range(9) if i + j > 2
            ))

            # BTTS from score matrix
            model_btts = float(dc_pred.score_matrix[1:, 1:].sum())

            # O/U 1.5
            model_o15 = float(sum(
                dc_pred.score_matrix[i, j]
                for i in range(9) for j in range(9) if i + j > 1
            ))

            # O/U 3.5
            model_o35 = float(sum(
                dc_pred.score_matrix[i, j]
                for i in range(9) for j in range(9) if i + j > 3
            ))

            # Test O/U 2.5 with score matrix
            for name, model_p, fair_p, best_o, won in [
                ("over_25", model_o25, fair_over, max_o25, total_goals > 2),
                ("under_25", 1 - model_o25, fair_under, max_u25, total_goals <= 2),
            ]:
                if fair_p > 0 and best_o > 1.0:
                    edge = ((model_p - fair_p) / fair_p) * 100
                    if edge >= 5.0:
                        H["H10_ou15"].append((won, best_o))

            # For O/U 1.5 and 3.5, we don't have odds so we use O/U 2.5 odds as proxy
            # Actually skip these - no odds available

        # Fortress detection for H2 enhancement
        # (tracked separately, not a bet)

    # ═══════ PRINT RESULTS ═══════
    print(f"\n  {'─'*72}")
    print(f"  RESULTS")
    print(f"  {'─'*72}")

    print_result("BASELINE: DC(0.65)+ELO(0.35), edge>=5%", roi_stats(H["baseline"]))
    print()
    print_result("H1: Form ELO (K=64 vs K=32)", roi_stats(H["H1"]))
    print_result("H2: Home/Away ELO split", roi_stats(H["H2"]))

    if h3_clv["total"] > 0:
        clv_rate = h3_clv["correct"] / h3_clv["total"] * 100
        avg_mag = np.mean(h3_clv["magnitude"]) * 100
        print(f"\n  H3: CLOSING LINE VALUE")
        print(f"      Line prediction accuracy: {clv_rate:.1f}% ({h3_clv['correct']}/{h3_clv['total']})")
        print(f"      Avg line movement: {avg_mag:.1f}pp")
        print(f"      (>50% = model predicts direction of smart money)")
    print_result("H3: Edge vs CLOSING odds (harder test)", roi_stats(H["H3"]))

    print()
    print_result("H4: Early season only (matchday 1-6, edge>=3%)", roi_stats(H["H4"]))
    print_result("H5: DC half-life 90 days (vs 180)", roi_stats(H["H5"]))
    print_result("H6: Promoted/new teams (< 40 matches, edge>=3%)", roi_stats(H["H6"]))

    print()
    print_result("H7: Asian Handicap (edge>=5%)", roi_stats(H["H7"]))
    if H["H7_lines"]:
        print(f"      By line:")
        for line in sorted(H["H7_lines"].keys()):
            bets = H["H7_lines"][line]
            s = roi_stats([(w, o) for w, o, _ in bets])
            if s["n"] >= 5:
                print(f"        AH {line:+.2f}: {s['n']:>4} bets, ROI {s['roi']:>+6.1f}%")

    print()
    print_result("H8: Big underdogs (odds>4.0, edge>=3%)", roi_stats(H["H8"]))
    print_result("H9: DC+ELO agree (disagreement<0.10, edge>=5%)", roi_stats(H["H9"]))
    print_result("H10: O/U 2.5 via score matrix (edge>=5%)", roi_stats(H["H10_ou15"]))

    # ─── Edge threshold analysis (from stored data, no recompute) ───
    print(f"\n  {'─'*72}")
    print(f"  EDGE THRESHOLD ANALYSIS")
    print(f"  {'─'*72}")
    all_edge_bets = H["baseline_with_edge"]
    for min_e in [0.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0]:
        filtered = [(w, o) for w, o, e, p in all_edge_bets if e >= min_e]
        print_result(f"Edge >= {min_e:>4.0f}%", roi_stats(filtered))

    # ─── PROBABILITY BAND ANALYSIS ───
    print(f"\n  {'─'*72}")
    print(f"  PROBABILITY BAND ANALYSIS (model prob x edge)")
    print(f"  {'─'*72}")

    # By probability band (any positive edge)
    prob_bands = [
        (0.0, 0.30, "Longshots (0-30%)"),
        (0.30, 0.45, "Underdogs (30-45%)"),
        (0.45, 0.55, "Coin-flip (45-55%)"),
        (0.55, 0.65, "Slight fav (55-65%)"),
        (0.65, 0.75, "Favorites (65-75%)"),
        (0.75, 1.01, "Strong fav (75%+)"),
    ]

    print(f"\n  --- Any positive edge (edge > 0%) ---")
    for lo, hi, label in prob_bands:
        filtered = [(w, o) for w, o, e, p in all_edge_bets if lo <= p < hi and e > 0]
        print_result(f"{label}", roi_stats(filtered))

    print(f"\n  --- Edge >= 3% ---")
    for lo, hi, label in prob_bands:
        filtered = [(w, o) for w, o, e, p in all_edge_bets if lo <= p < hi and e >= 3.0]
        print_result(f"{label}", roi_stats(filtered))

    print(f"\n  --- Edge >= 5% ---")
    for lo, hi, label in prob_bands:
        filtered = [(w, o) for w, o, e, p in all_edge_bets if lo <= p < hi and e >= 5.0]
        print_result(f"{label}", roi_stats(filtered))

    print(f"\n  --- Edge >= 10% ---")
    for lo, hi, label in prob_bands:
        filtered = [(w, o) for w, o, e, p in all_edge_bets if lo <= p < hi and e >= 10.0]
        print_result(f"{label}", roi_stats(filtered))

    # The user's hypothesis: strong favorites (75%+) with any edge
    print(f"\n  {'─'*72}")
    print(f"  USER HYPOTHESIS: Strong favorites (prob >= 75%) + positive edge")
    print(f"  {'─'*72}")
    for min_e in [0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0]:
        filtered = [(w, o) for w, o, e, p in all_edge_bets if p >= 0.75 and e >= min_e]
        print_result(f"Prob >= 75% & Edge >= {min_e:.0f}%", roi_stats(filtered))

    # Also test 65%+ and 60%+
    print()
    for min_prob in [0.60, 0.65, 0.70, 0.75]:
        for min_e in [3.0, 5.0, 10.0]:
            filtered = [(w, o) for w, o, e, p in all_edge_bets if p >= min_prob and e >= min_e]
            print_result(f"Prob >= {min_prob*100:.0f}% & Edge >= {min_e:.0f}%", roi_stats(filtered))


def _ensemble(dc_pred, elo_probs, w_dc, w_elo):
    h = w_dc * dc_pred.home_win + w_elo * elo_probs["home"]
    d = w_dc * dc_pred.draw + w_elo * elo_probs["draw"]
    a = w_dc * dc_pred.away_win + w_elo * elo_probs["away"]
    t = h + d + a
    return {"home": h/t, "draw": d/t, "away": a/t}


def _check_1x2_edge(bets_list, ens, fair_h, fair_d, fair_a,
                     max_h, max_d, max_a, outcome, min_edge=5.0):
    for name, model_p, fair_p, best_o, win_idx in [
        ("home", ens["home"], fair_h, max_h, 0),
        ("draw", ens["draw"], fair_d, max_d, 1),
        ("away", ens["away"], fair_a, max_a, 2),
    ]:
        if fair_p <= 0 or best_o <= 1.0:
            continue
        edge = ((model_p - fair_p) / fair_p) * 100
        if edge >= min_edge:
            won = outcome == win_idx
            bets_list.append((won, best_o))


def _check_1x2_edge_with_data(bets_list, ens, fair_h, fair_d, fair_a,
                               max_h, max_d, max_a, outcome, min_edge=0.0):
    for name, model_p, fair_p, best_o, win_idx in [
        ("home", ens["home"], fair_h, max_h, 0),
        ("draw", ens["draw"], fair_d, max_d, 1),
        ("away", ens["away"], fair_a, max_a, 2),
    ]:
        if fair_p <= 0 or best_o <= 1.0:
            continue
        edge = ((model_p - fair_p) / fair_p) * 100
        if edge >= min_edge:
            won = outcome == win_idx
            bets_list.append((won, best_o, edge, model_p))


def _update_home_away_elo(elo_dict, match):
    """Maintain separate home and away ELO ratings."""
    home = match["home_team"]
    away = match["away_team"]

    if home not in elo_dict:
        elo_dict[home] = {"home_elo": 1500.0, "away_elo": 1500.0}
    if away not in elo_dict:
        elo_dict[away] = {"home_elo": 1500.0, "away_elo": 1500.0}

    home_r = elo_dict[home]["home_elo"]
    away_r = elo_dict[away]["away_elo"]

    expected_home = 1.0 / (1.0 + 10 ** ((away_r - home_r - 80) / 400))
    expected_away = 1.0 - expected_home

    if match["home_score"] > match["away_score"]:
        actual_h, actual_a = 1.0, 0.0
    elif match["home_score"] < match["away_score"]:
        actual_h, actual_a = 0.0, 1.0
    else:
        actual_h, actual_a = 0.5, 0.5

    k = 40
    elo_dict[home]["home_elo"] += k * (actual_h - expected_home)
    elo_dict[away]["away_elo"] += k * (actual_a - expected_away)


def _predict_home_away_elo(elo_dict, home_team, away_team):
    """Predict using home/away split ELO."""
    hr = elo_dict.get(home_team, {"home_elo": 1500})["home_elo"]
    ar = elo_dict.get(away_team, {"away_elo": 1500})["away_elo"]

    expected_home = 1.0 / (1.0 + 10 ** ((ar - hr - 80) / 400))

    elo_diff = abs(hr - ar)
    draw_prob = max(0.10, min(0.35, 0.28 - elo_diff / 2500))
    remaining = 1.0 - draw_prob

    return {
        "home": remaining * expected_home,
        "draw": draw_prob,
        "away": remaining * (1.0 - expected_home),
    }


def _prob_cover_ah(score_matrix, ah_line):
    """P(home_goals - away_goals > -ah_line) from score matrix."""
    n = score_matrix.shape[0]
    prob = 0.0
    for i in range(n):
        for j in range(n):
            diff = i - j
            # Home covers if diff + ah_line > 0
            if diff + ah_line > 0:
                prob += score_matrix[i, j]
            elif diff + ah_line == 0:
                prob += score_matrix[i, j] * 0.5  # push = half
    return prob


def _ah_won(goal_diff, ah_line, side):
    """Did the AH bet win?"""
    if side == "home":
        effective = goal_diff + ah_line
    else:
        effective = -(goal_diff + ah_line)

    if effective > 0:
        return True
    elif effective == 0:
        return None  # push, treat as half won
    return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default="ligue_1")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2020, 2021, 2022, 2023, 2024])
    args = parser.parse_args()
    run_all_hypotheses(args.league, args.seasons)
