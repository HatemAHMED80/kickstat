#!/usr/bin/env python3
"""Hyperparameter tuning for XGBoost stacking model using Optuna.

Optimizes for best ROI on validation set while maintaining calibration.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import optuna
from loguru import logger
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data, build_odds_lookup
from src.data.odds_api import remove_margin
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.ensemble import EnsemblePredictor
from src.models.features import MatchHistory, compute_features, features_to_array
from src.models.xgb_model import XGBStackingModel
from src.evaluation.calibration import evaluate


def objective(trial: optuna.Trial, matches: list[dict], odds_data: dict) -> float:
    """Optuna objective: maximize ROI while keeping Brier < 0.62.

    Returns negative ROI (Optuna minimizes).
    """
    # Hyperparameters to tune
    max_depth = trial.suggest_int("max_depth", 2, 6)
    learning_rate = trial.suggest_float("learning_rate", 0.01, 0.2, log=True)
    n_estimators = trial.suggest_int("n_estimators", 100, 400, step=50)
    min_child_weight = trial.suggest_int("min_child_weight", 3, 15)
    subsample = trial.suggest_float("subsample", 0.6, 0.95)
    colsample_bytree = trial.suggest_float("colsample_bytree", 0.6, 0.95)
    reg_alpha = trial.suggest_float("reg_alpha", 0.0, 2.0)
    reg_lambda = trial.suggest_float("reg_lambda", 1.0, 5.0)

    # Scale pos weight for class imbalance (helps with home overconfidence)
    scale_pos_weight = trial.suggest_float("scale_pos_weight", 0.5, 2.0)

    # Run backtest with these hyperparameters
    matches = sorted(matches, key=lambda m: m["kickoff"])
    n = len(matches)
    min_training = 100
    refit_interval = 30
    xgb_retrain_interval = 60
    min_edge = 5.0

    all_probs = []
    all_outcomes = []
    betting_results = []
    odds_matched = 0

    # Build ELO + history up to min_training
    elo = EloRating()
    history = MatchHistory()
    for m in matches[:min_training]:
        elo.update(EloMatch(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
        ))
        history.add_match(m)

    dc = None
    xgb_model = XGBStackingModel(
        max_depth=max_depth,
        learning_rate=learning_rate,
        n_estimators=n_estimators,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        reg_alpha=reg_alpha,
        reg_lambda=reg_lambda,
    )
    xgb_training_X: list[np.ndarray] = []
    xgb_training_y: list[int] = []

    for i in range(min_training, n):
        test = matches[i]

        # Phase 1: Process previous match
        if i > min_training:
            prev = matches[i - 1]

            if dc is not None:
                prev_features = compute_features(
                    prev["home_team"], prev["away_team"],
                    prev["kickoff"], history,
                    dc_model=dc, elo_model=elo,
                )
                prev_hs, prev_as = prev["home_score"], prev["away_score"]
                prev_outcome = 0 if prev_hs > prev_as else (1 if prev_hs == prev_as else 2)
                xgb_training_X.append(features_to_array(prev_features))
                xgb_training_y.append(prev_outcome)

            history.add_match(prev)
            elo.update(EloMatch(
                home_team=prev["home_team"], away_team=prev["away_team"],
                home_goals=prev["home_score"], away_goals=prev["away_score"],
            ))

        # Phase 2: Refit models
        if dc is None or (i - min_training) % refit_interval == 0:
            dc_train = [
                MatchResult(
                    home_team=m["home_team"], away_team=m["away_team"],
                    home_goals=m["home_score"], away_goals=m["away_score"],
                    date=m["kickoff"],
                )
                for m in matches[:i]
            ]
            dc = DixonColesModel()
            try:
                dc.fit(dc_train)
            except ValueError:
                continue

        # XGBoost retrain
        if (len(xgb_training_X) >= XGBStackingModel.MIN_TRAINING_SAMPLES
                and (i - min_training) % xgb_retrain_interval == 0):
            X_arr = np.array(xgb_training_X)
            y_arr = np.array(xgb_training_y)
            split = int(len(X_arr) * 0.8)
            xgb_model.fit(
                X_arr[:split], y_arr[:split],
                X_val=X_arr[split:], y_val=y_arr[split:],
            )

        # Phase 3: Predict
        match_features = None
        if dc is not None:
            match_features = compute_features(
                test["home_team"], test["away_team"],
                test["kickoff"], history,
                dc_model=dc, elo_model=elo,
            )

        ensemble = EnsemblePredictor(dc, elo, 0.65, 0.35, xgb_model=xgb_model)
        pred = ensemble.predict(
            test["home_team"], test["away_team"],
            match_features=match_features,
        )

        probs = np.array([pred.home_prob, pred.draw_prob, pred.away_prob])
        all_probs.append(probs)

        # Actual outcome
        hs, aws = test["home_score"], test["away_score"]
        if hs > aws:
            outcome = 0
        elif hs == aws:
            outcome = 1
        else:
            outcome = 2
        all_outcomes.append(outcome)

        # Phase 4: Edge calculation
        date_str = str(test["kickoff"])[:10]
        match_key = f"{test['home_team']}_vs_{test['away_team']}_{date_str}"
        if match_key in odds_data:
            odds_matched += 1
            odds = odds_data[match_key]

            fair = remove_margin(
                odds["home_odds"], odds["draw_odds"], odds["away_odds"]
            )

            markets = [
                ("home", pred.home_prob, fair["home"],
                 odds.get("best_home", odds["home_odds"])),
                ("draw", pred.draw_prob, fair["draw"],
                 odds.get("best_draw", odds["draw_odds"])),
                ("away", pred.away_prob, fair["away"],
                 odds.get("best_away", odds["away_odds"])),
            ]

            for market_name, model_p, fair_p, best_odds in markets:
                if fair_p <= 0 or best_odds <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100

                if edge >= min_edge:
                    won = (
                        (market_name == "home" and outcome == 0)
                        or (market_name == "draw" and outcome == 1)
                        or (market_name == "away" and outcome == 2)
                    )
                    pnl = (best_odds - 1.0) if won else -1.0
                    betting_results.append({"pnl": pnl, "market": market_name})

    # Calibration
    probs_array = np.array(all_probs)
    outcomes_array = np.array(all_outcomes)
    cal = evaluate(probs_array, outcomes_array)

    # Betting stats
    total_pnl = sum(b["pnl"] for b in betting_results)
    n_bets = len(betting_results)
    roi = total_pnl / n_bets if n_bets > 0 else -1.0

    # Penalty if calibration is bad
    if cal.brier_score > 0.62:
        penalty = 1.0  # Heavy penalty
    else:
        penalty = 0.0

    # Report intermediate values for pruning
    trial.report(roi, step=0)

    # Return negative ROI (Optuna minimizes) + penalty
    return -roi + penalty


def main():
    parser = argparse.ArgumentParser(description="Tune XGBoost hyperparameters")
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2020, 2021, 2022, 2023, 2024],
        help="Seasons to include (default: 2020-2024)"
    )
    parser.add_argument("--league", default="ligue_1", help="League (default: ligue_1)")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of trials (default: 50)")
    parser.add_argument("--timeout", type=int, default=7200, help="Timeout in seconds (default: 2h)")
    args = parser.parse_args()

    cache_dir = PROJECT_ROOT / "data" / "historical"

    # Load data
    logger.info(f"Loading {args.league} seasons {args.seasons}")
    matches = load_historical_data(args.league, args.seasons, cache_dir)
    odds_data = build_odds_lookup(matches, odds_source="pinnacle")

    logger.info(f"Starting hyperparameter optimization with {args.n_trials} trials")

    # Create study
    study = optuna.create_study(
        direction="minimize",  # Minimize negative ROI
        sampler=TPESampler(seed=42),
        pruner=MedianPruner(n_startup_trials=10, n_warmup_steps=5),
    )

    # Optimize
    study.optimize(
        lambda trial: objective(trial, matches, odds_data),
        n_trials=args.n_trials,
        timeout=args.timeout,
        show_progress_bar=True,
    )

    # Results
    print("\n" + "=" * 70)
    print("  HYPERPARAMETER OPTIMIZATION RESULTS")
    print("=" * 70)

    best_trial = study.best_trial
    print(f"\n  Best ROI: {-best_trial.value:.2%}")
    print(f"  Trial number: {best_trial.number}")

    print("\n  Best hyperparameters:")
    for key, value in best_trial.params.items():
        print(f"    {key:>20}: {value}")

    # Save results
    results_dir = PROJECT_ROOT / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_path = results_dir / "xgb_hyperparameter_tuning.json"
    with open(results_path, "w") as f:
        json.dump({
            "best_params": best_trial.params,
            "best_roi": -best_trial.value,
            "n_trials": len(study.trials),
            "all_trials": [
                {
                    "number": t.number,
                    "params": t.params,
                    "value": t.value,
                    "roi": -t.value,
                }
                for t in study.trials
            ],
        }, f, indent=2)

    print(f"\n  Results saved to {results_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
