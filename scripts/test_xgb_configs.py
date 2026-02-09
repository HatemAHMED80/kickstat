#!/usr/bin/env python3
"""Quick test of 3 targeted XGBoost configurations to reduce home overconfidence.

Compares:
- Config A: More regularization (conservative)
- Config B: Class balancing (focus on draws/aways)
- Config C: Early stopping (prevent overfitting)
"""

import sys
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data, build_odds_lookup
from scripts.backtest_with_odds import run_backtest


def main():
    cache_dir = PROJECT_ROOT / "data" / "historical"

    logger.info("Loading data...")
    matches = load_historical_data("ligue_1", [2022, 2023, 2024], cache_dir)
    odds_data = build_odds_lookup(matches, odds_source="pinnacle")

    configs = {
        "baseline": {
            "max_depth": 4,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "min_child_weight": 5,
            "reg_lambda": 2.0,
        },
        "config_a_regularization": {
            "max_depth": 3,
            "learning_rate": 0.03,
            "n_estimators": 300,
            "min_child_weight": 10,
            "reg_lambda": 4.0,
        },
        "config_b_class_balance": {
            "max_depth": 4,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "min_child_weight": 5,
            "reg_lambda": 2.0,
            # Note: scale_pos_weight would need XGBClassifier modification
        },
        "config_c_early_stop": {
            "max_depth": 5,
            "learning_rate": 0.1,
            "n_estimators": 500,
            "min_child_weight": 5,
            "reg_lambda": 2.0,
            "early_stopping_rounds": 10,
        },
    }

    results_summary = []

    for name, config in configs.items():
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing: {name}")
        logger.info(f"{'='*70}")

        # Note: This would require modifying XGBStackingModel to accept these params
        # For now, just print the config
        logger.info(f"Config: {config}")

        # Uncomment when XGBStackingModel supports dynamic params:
        # result = run_backtest(
        #     matches, odds_data,
        #     use_xgb=True,
        #     xgb_params=config,
        # )
        #
        # results_summary.append({
        #     "config": name,
        #     "roi": result["betting"]["roi"],
        #     "brier": result["calibration"]["brier_score"],
        #     "home_roi": result["betting"]["by_market"]["home"]["roi"],
        #     "draw_roi": result["betting"]["by_market"]["draw"]["roi"],
        #     "away_roi": result["betting"]["by_market"]["away"]["roi"],
        # })

    # Print comparison
    print("\n" + "="*70)
    print("  CONFIGURATION COMPARISON")
    print("="*70)
    print("\nTo test these configs, modify src/models/xgb_model.py __init__ params")
    print("and run: python scripts/backtest_with_odds.py --seasons 2022 2023 2024")


if __name__ == "__main__":
    main()
