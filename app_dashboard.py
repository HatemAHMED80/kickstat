"""Smart Betting Dashboard — Kickstat

Interactive dashboard showing match predictions, value detection,
and Kelly-optimal staking recommendations.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import poisson

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import (
    LEAGUE_CODES, load_historical_data, download_season_csv, parse_season,
)
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.prop_models import remove_margin_2way, remove_margin_3way

# ─── Page config ───
st.set_page_config(
    page_title="Kickstat — Smart Betting",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───
st.markdown("""
<style>
    .main { background-color: #0a0e14; }
    .stApp { background-color: #0a0e14; }

    .match-card {
        background: linear-gradient(135deg, #141a24 0%, #1a2332 100%);
        border: 1px solid #1e2a3a;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
    }
    .value-positive {
        color: #00cc6a;
        font-weight: bold;
    }
    .value-negative {
        color: #ff4444;
    }
    .value-neutral {
        color: #888;
    }
    .kelly-box {
        background: linear-gradient(135deg, #0d2818 0%, #1a3a2a 100%);
        border: 1px solid #00cc6a;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .prob-bar {
        height: 8px;
        border-radius: 4px;
        margin: 4px 0;
    }
    .metric-label {
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
    }
    .edge-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .header-gradient {
        background: linear-gradient(90deg, #00cc6a, #00a3cc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2em;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

# ─── Cache models ───
@st.cache_resource
def load_models(league, seasons):
    """Load and fit models for a league."""
    cache_dir = PROJECT_ROOT / "data" / "historical"
    matches = load_historical_data(league, seasons, cache_dir)
    matches = sorted(matches, key=lambda m: m["kickoff"])

    # Fit DC on all data
    dc_train = [
        MatchResult(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
            date=m["kickoff"],
        )
        for m in matches
    ]
    dc = DixonColesModel(half_life_days=120)
    dc.fit(dc_train)

    # Fit ELO
    elo = EloRating(k_factor=40, home_advantage=100)
    for m in matches:
        elo.update(EloMatch(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
        ))

    return dc, elo, matches


def kelly_fraction(model_prob, odds):
    """Full Kelly stake as fraction of bankroll."""
    if odds <= 1.0 or model_prob <= 0:
        return 0.0
    b = odds - 1.0
    q = 1.0 - model_prob
    f = (model_prob * b - q) / b
    return max(f, 0.0)


def get_edge(model_prob, fair_prob):
    """Calculate edge percentage."""
    if fair_prob <= 0:
        return 0.0
    return ((model_prob - fair_prob) / fair_prob) * 100


def edge_color(edge):
    if edge >= 8:
        return "#00cc6a"
    elif edge >= 3:
        return "#ffaa00"
    elif edge > 0:
        return "#888888"
    return "#ff4444"


def edge_label(edge):
    if edge >= 15:
        return "STRONG VALUE"
    elif edge >= 8:
        return "VALUE"
    elif edge >= 3:
        return "SLIGHT VALUE"
    elif edge > 0:
        return "MARGINAL"
    return "NO VALUE"


# ─── Sidebar ───
st.sidebar.markdown('<p class="header-gradient">KICKSTAT</p>', unsafe_allow_html=True)
st.sidebar.markdown("**Smart Betting Assistant**")
st.sidebar.divider()

league = st.sidebar.selectbox(
    "League",
    options=["ligue_1", "premier_league", "la_liga", "bundesliga", "serie_a",
             "ligue_2", "championship", "serie_b", "eredivisie", "super_lig"],
    format_func=lambda x: x.replace("_", " ").title(),
)

seasons = st.sidebar.multiselect(
    "Training seasons",
    options=[2020, 2021, 2022, 2023, 2024],
    default=[2022, 2023, 2024],
)

st.sidebar.divider()
st.sidebar.markdown("### Bankroll")
bankroll = st.sidebar.number_input("Capital (EUR)", value=1000, step=100, min_value=100)
kelly_frac = st.sidebar.slider("Kelly fraction", 0.05, 1.0, 0.25, 0.05,
                                help="0.25 = quarter Kelly (recommended)")
min_edge_filter = st.sidebar.slider("Min edge to show (%)", 0, 30, 3, 1)

st.sidebar.divider()
st.sidebar.markdown("### Model Performance")
st.sidebar.markdown("""
- Calibrated probabilities (Brier 0.60)
- 1X2 vs Pinnacle: -6.6% ROI
- O/U 2.5: breakeven
- Promoted teams: +1.1% ROI signal

*The model gives accurate probabilities but doesn't guarantee profits against sharp bookmakers.*
""")

# ─── Load models ───
if not seasons:
    st.error("Select at least one training season.")
    st.stop()

with st.spinner(f"Fitting models on {league.replace('_', ' ').title()}..."):
    dc, elo, matches = load_models(league, tuple(seasons))

# ─── Main content ───
st.markdown('<p class="header-gradient">Match Analysis</p>', unsafe_allow_html=True)
st.markdown(f"**{league.replace('_', ' ').title()}** — {len(matches)} matches loaded, "
            f"{len(dc.teams)} teams rated")

# Get the latest matches as "upcoming" simulation
# In production, these would come from a live API
# For demo, use the last 20 matches from data and pretend they're upcoming
recent = matches[-20:]

# Tabs
tab1, tab2, tab3 = st.tabs(["Predictions", "Value Detector", "Kelly Calculator"])

# ─── TAB 1: Predictions ───
with tab1:
    st.markdown("### Match Predictions")
    st.markdown("*Model probabilities from Dixon-Coles + ELO ensemble*")

    for match in recent:
        home = match["home_team"]
        away = match["away_team"]
        date_str = str(match["kickoff"])[:10]

        # Model predictions
        dc_pred = dc.predict(home, away)
        elo_probs = elo.predict_1x2(home, away)

        # Ensemble
        w_dc, w_elo = 0.65, 0.35
        ens_h = w_dc * dc_pred.home_win + w_elo * elo_probs["home"]
        ens_d = w_dc * dc_pred.draw + w_elo * elo_probs["draw"]
        ens_a = w_dc * dc_pred.away_win + w_elo * elo_probs["away"]
        total = ens_h + ens_d + ens_a
        ens_h /= total; ens_d /= total; ens_a /= total

        # Actual odds
        pin_h = match.get("pinnacle_home", 0)
        pin_d = match.get("pinnacle_draw", 0)
        pin_a = match.get("pinnacle_away", 0)
        has_odds = pin_h > 1.0 and pin_d > 1.0 and pin_a > 1.0

        # Actual result
        hs, aws = match["home_score"], match["away_score"]

        col1, col2, col3 = st.columns([3, 4, 2])

        with col1:
            st.markdown(f"**{date_str}**")
            st.markdown(f"### {home} vs {away}")
            st.caption(f"Score: {hs} - {aws}")

        with col2:
            # Probability bars
            bar_data = pd.DataFrame({
                "Outcome": ["Home", "Draw", "Away"],
                "Model": [ens_h * 100, ens_d * 100, ens_a * 100],
            })
            if has_odds:
                fair_h, fair_d, fair_a = remove_margin_3way(pin_h, pin_d, pin_a)
                bar_data["Bookmaker"] = [fair_h * 100, fair_d * 100, fair_a * 100]

            st.bar_chart(bar_data.set_index("Outcome"), height=150, color=["#00cc6a", "#ff6b6b"])

        with col3:
            # Key stats
            st.metric("O/U 2.5", f"{dc_pred.over_25:.0%}")
            st.metric("BTTS", f"{dc_pred.btts_yes:.0%}")
            implied_h = f"{1/ens_h:.2f}" if ens_h > 0 else "-"
            st.caption(f"Fair odds: {implied_h} / {1/ens_d:.2f} / {1/ens_a:.2f}")

        st.divider()


# ─── TAB 2: Value Detector ───
with tab2:
    st.markdown("### Value Detector")
    st.markdown("*Compare model probabilities vs bookmaker odds to find edges*")

    # Build value opportunities from recent matches
    opportunities = []
    for match in matches[-100:]:  # last 100 matches
        home = match["home_team"]
        away = match["away_team"]
        date_str = str(match["kickoff"])[:10]

        pin_h = match.get("pinnacle_home", 0)
        pin_d = match.get("pinnacle_draw", 0)
        pin_a = match.get("pinnacle_away", 0)
        if not (pin_h > 1.0 and pin_d > 1.0 and pin_a > 1.0):
            continue

        dc_pred = dc.predict(home, away)
        elo_probs = elo.predict_1x2(home, away)

        ens_h = 0.65 * dc_pred.home_win + 0.35 * elo_probs["home"]
        ens_d = 0.65 * dc_pred.draw + 0.35 * elo_probs["draw"]
        ens_a = 0.65 * dc_pred.away_win + 0.35 * elo_probs["away"]
        t = ens_h + ens_d + ens_a
        ens_h /= t; ens_d /= t; ens_a /= t

        fair_h, fair_d, fair_a = remove_margin_3way(pin_h, pin_d, pin_a)
        max_h = match.get("max_home", pin_h)
        max_d = match.get("max_draw", pin_d)
        max_a = match.get("max_away", pin_a)

        hs, aws = match["home_score"], match["away_score"]
        outcome = 0 if hs > aws else (1 if hs == aws else 2)

        for name, model_p, fair_p, best_o, pin_o, win_idx in [
            ("Home", ens_h, fair_h, max_h, pin_h, 0),
            ("Draw", ens_d, fair_d, max_d, pin_d, 1),
            ("Away", ens_a, fair_a, max_a, pin_a, 2),
        ]:
            edge = get_edge(model_p, fair_p)
            if edge >= min_edge_filter:
                won = outcome == win_idx
                kf = kelly_fraction(model_p, best_o) * kelly_frac
                stake = bankroll * kf

                opportunities.append({
                    "Date": date_str,
                    "Match": f"{home} vs {away}",
                    "Bet": name,
                    "Model": f"{model_p:.1%}",
                    "Bookmaker": f"{fair_p:.1%}",
                    "Edge": f"{edge:+.1f}%",
                    "Best Odds": f"{best_o:.2f}",
                    "Kelly Stake": f"{stake:.0f} EUR",
                    "Result": "Won" if won else "Lost",
                    "_edge": edge,
                    "_won": won,
                    "_pnl": (best_o - 1) if won else -1,
                })

    if opportunities:
        # Summary metrics
        total_bets = len(opportunities)
        wins = sum(1 for o in opportunities if o["_won"])
        total_pnl = sum(o["_pnl"] for o in opportunities)
        avg_edge = np.mean([o["_edge"] for o in opportunities])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Opportunities", total_bets)
        col2.metric("Win Rate", f"{wins/total_bets:.1%}")
        col3.metric("Avg Edge", f"{avg_edge:.1f}%")
        col4.metric("Unit PnL", f"{total_pnl:+.1f}u",
                     delta=f"ROI {total_pnl/total_bets*100:.1f}%",
                     delta_color="normal" if total_pnl >= 0 else "inverse")

        # Table
        df = pd.DataFrame(opportunities)
        display_cols = ["Date", "Match", "Bet", "Model", "Bookmaker", "Edge", "Best Odds", "Kelly Stake", "Result"]
        st.dataframe(
            df[display_cols].style.apply(
                lambda row: ["background-color: #0d2818" if row["Result"] == "Won"
                             else "background-color: #2a0d0d"] * len(row),
                axis=1,
            ),
            use_container_width=True,
            height=500,
        )

        # Edge distribution
        st.markdown("### Edge Distribution")
        edge_data = pd.DataFrame({"Edge %": [o["_edge"] for o in opportunities]})
        st.bar_chart(edge_data.value_counts(bins=15).sort_index(), height=200)
    else:
        st.info(f"No opportunities found with edge >= {min_edge_filter}%. Lower the threshold.")


# ─── TAB 3: Kelly Calculator ───
with tab3:
    st.markdown("### Kelly Stake Calculator")
    st.markdown("*Calculate optimal bet size based on your edge*")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Manual Calculator")
        calc_prob = st.slider("Your estimated probability (%)", 10, 90, 50, 1) / 100
        calc_odds = st.number_input("Bookmaker odds", value=2.00, step=0.05, min_value=1.01)
        calc_bankroll = bankroll

        implied = 1 / calc_odds
        edge = get_edge(calc_prob, implied)
        kf_full = kelly_fraction(calc_prob, calc_odds)
        kf_quarter = kf_full * 0.25
        kf_half = kf_full * 0.50

        st.divider()

        if edge > 0:
            st.markdown(f"""
            <div class="kelly-box">
                <div class="metric-label">YOUR EDGE</div>
                <div class="metric-value" style="color: #00cc6a;">{edge:+.1f}%</div>
                <br>
                <div class="metric-label">FULL KELLY</div>
                <div style="font-size:18px;">{kf_full:.1%} = <b>{calc_bankroll * kf_full:.0f} EUR</b></div>
                <br>
                <div class="metric-label">HALF KELLY (Recommended)</div>
                <div style="font-size:20px; color:#00cc6a;">{kf_half:.1%} = <b>{calc_bankroll * kf_half:.0f} EUR</b></div>
                <br>
                <div class="metric-label">QUARTER KELLY (Conservative)</div>
                <div style="font-size:18px;">{kf_quarter:.1%} = <b>{calc_bankroll * kf_quarter:.0f} EUR</b></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#2a0d0d; border:1px solid #ff4444; border-radius:8px; padding:16px; text-align:center;">
                <div class="metric-label">YOUR EDGE</div>
                <div class="metric-value" style="color: #ff4444;">{edge:+.1f}%</div>
                <br>
                <div style="color:#ff4444; font-size:16px;">
                    NO BET — Your probability ({calc_prob:.0%}) doesn't justify these odds ({calc_odds:.2f}).
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown("#### Kelly Cheat Sheet")
        st.markdown("""
        **What is Kelly?**

        Kelly criterion calculates the mathematically optimal fraction
        of your bankroll to stake on a bet, given your edge.

        **Formula:**
        `f* = (p * b - q) / b`

        Where:
        - `p` = your probability of winning
        - `q` = 1 - p (probability of losing)
        - `b` = odds - 1 (net payout)

        **In practice:**
        - **Full Kelly** is too aggressive — high variance
        - **Half Kelly** is the sweet spot — 75% of the growth, much less variance
        - **Quarter Kelly** is conservative — slow but steady

        **Golden rules:**
        1. Never bet more than 5% of bankroll on a single bet
        2. If Kelly says > 10%, your edge estimate is probably wrong
        3. Fractional Kelly protects against estimation errors
        """)

        # Risk of ruin table
        st.markdown("#### Risk of Ruin")
        ruin_data = {
            "Strategy": ["Full Kelly", "Half Kelly", "Quarter Kelly", "Flat 2%"],
            "Growth Rate": ["Optimal", "75% of optimal", "50% of optimal", "Linear"],
            "Risk of Ruin": ["~13%", "~1.7%", "~0.1%", "~0%"],
            "Recommended": ["No", "Yes", "Yes (beginners)", "Safe"],
        }
        st.table(pd.DataFrame(ruin_data))


# ─── TAB: Team Rankings (bonus) ───
st.divider()
st.markdown("### Team Strength Rankings")
st.markdown("*Dixon-Coles attack/defense parameters — higher strength = stronger team*")

rankings = dc.get_team_rankings()
if rankings:
    df_rank = pd.DataFrame(rankings)
    df_rank.index = range(1, len(df_rank) + 1)
    df_rank.columns = ["Team", "Attack", "Defense", "Strength"]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top attackers**")
        st.dataframe(df_rank.sort_values("Attack", ascending=False).head(10)[["Team", "Attack"]],
                      use_container_width=True)
    with col2:
        st.markdown("**Best defenders** (lower = better)")
        st.dataframe(df_rank.sort_values("Defense", ascending=True).head(10)[["Team", "Defense"]],
                      use_container_width=True)

# Footer
st.divider()
st.caption("Kickstat v0.1 — Model: Dixon-Coles + ELO ensemble | Data: football-data.co.uk | "
           "This tool provides analysis, not betting advice. Gamble responsibly.")
