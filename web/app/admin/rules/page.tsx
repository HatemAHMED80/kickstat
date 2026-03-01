"use client";

import { useState, useEffect, useMemo } from "react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type Bet = {
  m: string; // market
  p: number; // model_prob
  e: number; // edge_pct
  k: number; // kelly_pct
  w: number; // won (0/1)
  pnl: number;
  o: number; // best_odds
};

type BetGroup = {
  l: string; // league
  c: string; // config
  b: Bet[];
};

/* ------------------------------------------------------------------ */
/*  Defaults — miroir de generate_predictions_json.py                  */
/* ------------------------------------------------------------------ */

const BACKTEST_MARKETS = ["home", "draw", "away", "over25", "under25", "ah_home", "ah_away"] as const;

const DEFAULTS: Record<string, { edge: number; prob: number; enabled: boolean }> = {
  home:    { edge: 8,  prob: 42, enabled: true },
  draw:    { edge: 5,  prob: 28, enabled: true },
  away:    { edge: 15, prob: 40, enabled: true },
  over25:  { edge: 7,  prob: 58, enabled: true },
  under25: { edge: 10, prob: 50, enabled: true },
  ah_home: { edge: 8,  prob: 38, enabled: true },
  ah_away: { edge: 5,  prob: 55, enabled: true },
};

const MARKET_LABELS: Record<string, string> = {
  home: "Victoire domicile",
  draw: "Match nul",
  away: "Victoire exterieur",
  over25: "Over 2.5 buts",
  under25: "Under 2.5 buts",
  ah_home: "Asian Handicap dom",
  ah_away: "Asian Handicap ext",
};

const LEAGUE_LABELS: Record<string, string> = {
  premier_league: "Premier League",
  la_liga: "La Liga",
  bundesliga: "Bundesliga",
  serie_a: "Serie A",
  ligue_1: "Ligue 1",
};

/* ------------------------------------------------------------------ */
/*  Components                                                         */
/* ------------------------------------------------------------------ */

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm ${className}`}>
      {children}
    </div>
  );
}

function StatBox({ label, value, sub, color = "violet" }: { label: string; value: string; sub?: string; color?: string }) {
  const colorMap: Record<string, string> = {
    violet: "text-violet-300",
    green: "text-emerald-400",
    red: "text-red-400",
    amber: "text-amber-400",
    zinc: "text-zinc-400",
  };
  return (
    <div className="p-3 rounded-lg bg-white/[0.03] border border-white/10 text-center">
      <div className="text-[11px] text-zinc-500 mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${colorMap[color] || colorMap.violet}`}>{value}</div>
      {sub && <div className="text-[11px] text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function RulesPage() {
  const [data, setData] = useState<BetGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<string>("optimal");
  const [kellyMin, setKellyMin] = useState(1.0);

  // Per-market thresholds
  const [markets, setMarkets] = useState<Record<string, { edge: number; prob: number; enabled: boolean }>>(() => {
    const init: Record<string, { edge: number; prob: number; enabled: boolean }> = {};
    for (const m of BACKTEST_MARKETS) {
      init[m] = { ...DEFAULTS[m] };
    }
    return init;
  });

  // Load data
  useEffect(() => {
    fetch("/backtest_bets.json")
      .then((r) => r.json())
      .then((d: BetGroup[]) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Filter bets based on current thresholds
  const results = useMemo(() => {
    if (!data.length) return null;

    const groups = data.filter((g) => g.c === config);

    type MarketResult = { bets: number; wins: number; pnl: number };
    const byMarket: Record<string, MarketResult> = {};
    const byLeague: Record<string, Record<string, MarketResult>> = {};
    let totalBets = 0;
    let totalWins = 0;
    let totalPnl = 0;

    for (const m of BACKTEST_MARKETS) {
      byMarket[m] = { bets: 0, wins: 0, pnl: 0 };
    }

    for (const group of groups) {
      if (!byLeague[group.l]) {
        byLeague[group.l] = {};
        for (const m of BACKTEST_MARKETS) {
          byLeague[group.l][m] = { bets: 0, wins: 0, pnl: 0 };
        }
      }

      for (const bet of group.b) {
        const cfg = markets[bet.m];
        if (!cfg || !cfg.enabled) continue;
        if (bet.e < cfg.edge) continue;
        if (bet.p * 100 < cfg.prob) continue;
        if (bet.k < kellyMin) continue;

        byMarket[bet.m].bets++;
        byMarket[bet.m].wins += bet.w;
        byMarket[bet.m].pnl += bet.pnl;

        byLeague[group.l][bet.m].bets++;
        byLeague[group.l][bet.m].wins += bet.w;
        byLeague[group.l][bet.m].pnl += bet.pnl;

        totalBets++;
        totalWins += bet.w;
        totalPnl += bet.pnl;
      }
    }

    return { byMarket, byLeague, totalBets, totalWins, totalPnl };
  }, [data, config, markets, kellyMin]);

  function updateMarket(m: string, field: "edge" | "prob" | "enabled", value: number | boolean) {
    setMarkets((prev) => ({
      ...prev,
      [m]: { ...prev[m], [field]: value },
    }));
  }

  function resetDefaults() {
    const init: Record<string, { edge: number; prob: number; enabled: boolean }> = {};
    for (const m of BACKTEST_MARKETS) {
      init[m] = { ...DEFAULTS[m] };
    }
    setMarkets(init);
    setKellyMin(1.0);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-400">
        Chargement des donnees backtest...
      </div>
    );
  }

  const roi = results && results.totalBets > 0 ? (results.totalPnl / results.totalBets) * 100 : 0;
  const winRate = results && results.totalBets > 0 ? (results.totalWins / results.totalBets) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Simulateur de regles v8</h1>
          <p className="text-zinc-400 text-sm">
            Modifie les seuils et vois l&apos;impact sur les resultats du backtest (5 ligues, 2021-2025).
            Config optimale : <span className="text-emerald-400 font-semibold">+430.8u, +6.4% ROI</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={config}
            onChange={(e) => setConfig(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white"
          >
            <option value="optimal">OPTIMAL (best/market)</option>
            <option value="baseline">DC + ELO (baseline)</option>
            <option value="xgb">+ XGBoost (all)</option>
            <option value="xgb_draw">+ XGBoost (draw only)</option>
            <option value="xgb_cal">+ XGB + Calibration</option>
            <option value="hybrid">HYBRID</option>
          </select>
          <button
            onClick={resetDefaults}
            className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-zinc-400 hover:text-white hover:border-white/20 transition-colors"
          >
            Reset prod
          </button>
        </div>
      </div>

      {/* Global stats */}
      {results && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatBox label="Total paris" value={results.totalBets.toLocaleString()} />
          <StatBox
            label="Win rate"
            value={`${winRate.toFixed(1)}%`}
            color={winRate > 45 ? "green" : "zinc"}
          />
          <StatBox
            label="PnL"
            value={`${results.totalPnl >= 0 ? "+" : ""}${results.totalPnl.toFixed(1)}u`}
            color={results.totalPnl >= 0 ? "green" : "red"}
          />
          <StatBox
            label="ROI"
            value={`${roi >= 0 ? "+" : ""}${roi.toFixed(1)}%`}
            color={roi >= 0 ? "green" : "red"}
          />
        </div>
      )}

      {/* Market controls + results */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
            Seuils par marche
          </h2>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-zinc-500">Kelly min :</span>
            <input
              type="range"
              min={0}
              max={5}
              step={0.5}
              value={kellyMin}
              onChange={(e) => setKellyMin(parseFloat(e.target.value))}
              className="w-20 accent-violet-500"
            />
            <span className="font-mono text-violet-300 w-10">{kellyMin}%</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-zinc-400 border-b border-white/10">
                <th className="text-left py-2 pr-2 font-medium w-8"></th>
                <th className="text-left py-2 pr-4 font-medium">Marche</th>
                <th className="text-center py-2 px-2 font-medium">Edge min</th>
                <th className="text-center py-2 px-2 font-medium">Proba min</th>
                <th className="text-center py-2 px-2 font-medium">Paris</th>
                <th className="text-center py-2 px-2 font-medium">Win%</th>
                <th className="text-center py-2 px-2 font-medium">PnL</th>
                <th className="text-center py-2 px-2 font-medium">ROI</th>
              </tr>
            </thead>
            <tbody>
              {BACKTEST_MARKETS.map((m) => {
                const cfg = markets[m];
                const r = results?.byMarket[m];
                const mRoi = r && r.bets > 0 ? (r.pnl / r.bets) * 100 : 0;
                const mWin = r && r.bets > 0 ? (r.wins / r.bets) * 100 : 0;

                return (
                  <tr key={m} className={`border-b border-white/5 ${!cfg.enabled ? "opacity-40" : ""}`}>
                    <td className="py-2 pr-2">
                      <input
                        type="checkbox"
                        checked={cfg.enabled}
                        onChange={(e) => updateMarket(m, "enabled", e.target.checked)}
                        className="accent-violet-500 w-4 h-4"
                      />
                    </td>
                    <td className="py-2 pr-4 font-medium">{MARKET_LABELS[m]}</td>
                    <td className="py-2 px-2">
                      <div className="flex items-center justify-center gap-1">
                        <input
                          type="range"
                          min={0}
                          max={30}
                          step={1}
                          value={cfg.edge}
                          onChange={(e) => updateMarket(m, "edge", parseFloat(e.target.value))}
                          disabled={!cfg.enabled}
                          className="w-16 accent-violet-500"
                        />
                        <span className="font-mono text-violet-300 w-10 text-right">{cfg.edge}%</span>
                      </div>
                    </td>
                    <td className="py-2 px-2">
                      <div className="flex items-center justify-center gap-1">
                        <input
                          type="range"
                          min={0}
                          max={80}
                          step={5}
                          value={cfg.prob}
                          onChange={(e) => updateMarket(m, "prob", parseFloat(e.target.value))}
                          disabled={!cfg.enabled}
                          className="w-16 accent-violet-500"
                        />
                        <span className="font-mono text-violet-300 w-10 text-right">{cfg.prob}%</span>
                      </div>
                    </td>
                    <td className="py-2 px-2 text-center font-mono">
                      {r?.bets || 0}
                    </td>
                    <td className="py-2 px-2 text-center font-mono">
                      {r && r.bets > 0 ? `${mWin.toFixed(0)}%` : "-"}
                    </td>
                    <td className={`py-2 px-2 text-center font-mono font-semibold ${r && r.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {r && r.bets > 0 ? `${r.pnl >= 0 ? "+" : ""}${r.pnl.toFixed(1)}` : "-"}
                    </td>
                    <td className={`py-2 px-2 text-center font-mono font-semibold ${mRoi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {r && r.bets > 0 ? `${mRoi >= 0 ? "+" : ""}${mRoi.toFixed(1)}%` : "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Per-league breakdown */}
      {results && (
        <Card>
          <h2 className="text-lg font-semibold mb-4 bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
            Resultats par ligue
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(results.byLeague).map(([league, marketResults]) => {
              const leagueBets = Object.values(marketResults).reduce((s, r) => s + r.bets, 0);
              const leaguePnl = Object.values(marketResults).reduce((s, r) => s + r.pnl, 0);
              const leagueRoi = leagueBets > 0 ? (leaguePnl / leagueBets) * 100 : 0;

              return (
                <div key={league} className="p-4 rounded-lg bg-white/[0.03] border border-white/10">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium">{LEAGUE_LABELS[league] || league}</span>
                    <span className={`font-mono text-sm font-bold ${leagueRoi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {leagueRoi >= 0 ? "+" : ""}{leagueRoi.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-xs text-zinc-500 mb-2">
                    {leagueBets} paris | PnL {leaguePnl >= 0 ? "+" : ""}{leaguePnl.toFixed(1)}u
                  </div>
                  <div className="space-y-1">
                    {BACKTEST_MARKETS.filter((m) => markets[m].enabled && marketResults[m]?.bets > 0).map((m) => {
                      const r = marketResults[m];
                      const mRoi = r.bets > 0 ? (r.pnl / r.bets) * 100 : 0;
                      return (
                        <div key={m} className="flex justify-between text-xs">
                          <span className="text-zinc-400">{MARKET_LABELS[m]}</span>
                          <span className={`font-mono ${mRoi >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {r.bets} | {mRoi >= 0 ? "+" : ""}{mRoi.toFixed(1)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Confidence badges reference */}
      <Card>
        <h2 className="text-lg font-semibold mb-3 bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
          Badges de confiance
        </h2>
        <div className="flex flex-wrap gap-2">
          {[
            { label: "ULTRA_SAFE", range: ">= 85%", cls: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
            { label: "HIGH_SAFE", range: "75-85%", cls: "bg-green-500/20 text-green-300 border-green-500/30" },
            { label: "SAFE", range: "60-75%", cls: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
            { label: "VALUE", range: "50-60%", cls: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
            { label: "RISKY", range: "35-50%", cls: "bg-orange-500/20 text-orange-300 border-orange-500/30" },
            { label: "ULTRA_RISKY", range: "< 35%", cls: "bg-red-500/20 text-red-300 border-red-500/30" },
          ].map((b) => (
            <div key={b.label} className={`px-3 py-1.5 rounded-full border text-xs ${b.cls}`}>
              {b.label} <span className="opacity-70">{b.range}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
