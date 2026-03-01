'use client';

import { useState, useEffect } from 'react';
import NavBar from '../components/NavBar';
import { getSupabase } from '../lib/supabase';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface HistoryRecord {
  id: string;
  date: string;
  kickoff: string;
  home_team: string;
  away_team: string;
  league: string;
  recommended_bet: string;
  odds: number | null;
  model_prob: number | null;
  edge_pct: number | null;
  confidence_badge: string | null;
  home_score?: number;
  away_score?: number;
  won?: boolean | null;
  pnl?: number;
  resolved: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const BET_LABELS: Record<string, string> = {
  home: 'Victoire dom.',
  draw: 'Match nul',
  away: 'Victoire ext.',
  over15: '+1,5 buts',
  under15: '-1,5 buts',
  over25: '+2,5 buts',
  under25: '-2,5 buts',
  over35: '+3,5 buts',
  under35: '-3,5 buts',
  dc_1x: 'Double chance 1X',
  dc_x2: 'Double chance X2',
  dc_12: 'Double chance 12',
  dnb_home: 'DNB Domicile',
  dnb_away: 'DNB Extérieur',
  spread_home_m15: 'Handicap -1,5 Dom.',
  spread_away_p15: 'Handicap +1,5 Ext.',
  spread_home_m25: 'Handicap -2,5 Dom.',
  spread_away_p25: 'Handicap +2,5 Ext.',
};

const BADGE_COLORS: Record<string, string> = {
  ULTRA_SAFE: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  HIGH_SAFE: 'text-green-400 bg-green-500/10 border-green-500/30',
  SAFE: 'text-teal-400 bg-teal-500/10 border-teal-500/30',
  VALUE: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  RISKY: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  ULTRA_RISKY: 'text-red-400 bg-red-500/10 border-red-500/30',
};

function formatBet(bet: string): string {
  return BET_LABELS[bet] ?? bet;
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

function formatProb(p: number | null): string {
  if (p == null) return '—';
  return `${(p * 100).toFixed(0)}%`;
}

// ---------------------------------------------------------------------------
// Custom tooltip for the chart
// ---------------------------------------------------------------------------
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const roi = payload[0]?.value as number;
  return (
    <div className="bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-xs">
      <p className="text-zinc-400 mb-1">{label}</p>
      <p className={`font-bold ${roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        ROI cumulé : {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
      </p>
    </div>
  );
}

function BankrollTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const val = payload[0]?.value as number;
  const profit = val - 1000;
  return (
    <div className="bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-xs">
      <p className="text-zinc-400 mb-1">{label}</p>
      <p className={`font-bold ${val >= 1000 ? 'text-emerald-400' : 'text-red-400'}`}>
        Capital : {val.toLocaleString('fr-FR')} €
      </p>
      <p className={`text-[11px] ${profit >= 0 ? 'text-emerald-400/70' : 'text-red-400/70'}`}>
        {profit >= 0 ? '+' : ''}{profit.toLocaleString('fr-FR')} € de profit
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function HistoriquePage() {
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'won' | 'lost'>('all');
  const [leagueFilter, setLeagueFilter] = useState<string>('all');

  useEffect(() => {
    async function fetchAll() {
      try {
        const supabase = getSupabase();
        const PAGE = 1000;
        let all: HistoryRecord[] = [];
        let from = 0;

        while (true) {
          const { data, error } = await supabase
            .from('bets')
            .select('*')
            .eq('resolved', true)
            .order('date', { ascending: false })
            .range(from, from + PAGE - 1);

          if (error || !data) break;

          all = all.concat(data as HistoryRecord[]);
          if (data.length < PAGE) break;
          from += PAGE;
        }

        if (all.length > 0) {
          setHistory(all);
          setLoading(false);
          return;
        }
      } catch (e) {
        console.error('Supabase fetch failed:', e);
      }

      // Fallback to static JSON
      try {
        const res = await fetch('/history.json');
        const json: HistoryRecord[] = await res.json();
        setHistory(json);
      } catch (e) {
        console.error('History JSON fetch failed:', e);
      }
      setLoading(false);
    }

    fetchAll();
  }, []);

  // ---------------------------------------------------------------------------
  // Stats
  // ---------------------------------------------------------------------------
  const resolved = history.filter(h => h.resolved);
  const wins = resolved.filter(h => h.won === true).length;
  const losses = resolved.filter(h => h.won === false).length;
  const pushes = resolved.filter(h => h.won === null).length;
  const totalPnl = resolved.reduce((acc, h) => acc + (h.pnl ?? 0), 0);
  const roi = resolved.length > 0 ? (totalPnl / resolved.length) * 100 : 0;
  const winRate = (wins + pushes) > 0 && resolved.length > 0
    ? (wins / resolved.filter(h => h.won !== null).length) * 100
    : 0;

  // Unique leagues
  const leagues = Array.from(new Set(history.map(h => h.league)));

  // ---------------------------------------------------------------------------
  // ROI chart data (chronological — oldest first)
  // ---------------------------------------------------------------------------
  const chartData = (() => {
    const chrono = [...history].reverse().filter(h => h.resolved);
    let cumPnl = 0;
    return chrono.map((h, i) => {
      cumPnl += h.pnl ?? 0;
      const cumRoi = ((cumPnl / (i + 1)) * 100);
      return {
        label: formatDate(h.date),
        roi: parseFloat(cumRoi.toFixed(2)),
        bet: i + 1,
      };
    });
  })();

  // ---------------------------------------------------------------------------
  // Bankroll simulation: 1000€ de départ, mise fixe 10€ (1%) par pari
  // ---------------------------------------------------------------------------
  const STARTING_BANKROLL = 1000;
  const UNIT_SIZE = 10; // 1% du capital initial

  const bankrollData = (() => {
    const chrono = [...history].reverse().filter(h => h.resolved);
    let bankroll = STARTING_BANKROLL;
    let maxBankroll = STARTING_BANKROLL;
    let minBankroll = STARTING_BANKROLL;
    return chrono.map((h, i) => {
      bankroll += (h.pnl ?? 0) * UNIT_SIZE;
      bankroll = parseFloat(bankroll.toFixed(2));
      if (bankroll > maxBankroll) maxBankroll = bankroll;
      if (bankroll < minBankroll) minBankroll = bankroll;
      return {
        label: formatDate(h.date),
        bankroll,
        bet: i + 1,
        maxBankroll,
        minBankroll,
      };
    });
  })();

  const finalBankroll = bankrollData.length > 0 ? bankrollData[bankrollData.length - 1].bankroll : STARTING_BANKROLL;
  const totalProfit = finalBankroll - STARTING_BANKROLL;
  const bankrollROI = ((totalProfit / STARTING_BANKROLL) * 100);
  const maxDrawdown = (() => {
    let peak = STARTING_BANKROLL;
    let maxDd = 0;
    const chrono = [...history].reverse().filter(h => h.resolved);
    let bankroll = STARTING_BANKROLL;
    for (const h of chrono) {
      bankroll += (h.pnl ?? 0) * UNIT_SIZE;
      if (bankroll > peak) peak = bankroll;
      const dd = ((peak - bankroll) / peak) * 100;
      if (dd > maxDd) maxDd = dd;
    }
    return maxDd;
  })();

  // ---------------------------------------------------------------------------
  // Filtered table
  // ---------------------------------------------------------------------------
  const filtered = history.filter(h => {
    if (leagueFilter !== 'all' && h.league !== leagueFilter) return false;
    if (filter === 'won') return h.won === true;
    if (filter === 'lost') return h.won === false;
    return true;
  });

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      <NavBar />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-1">Historique des paris</h1>
          <p className="text-zinc-500 text-sm">Résultats réels — mis à jour automatiquement après chaque match</p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="text-center py-20 text-zinc-500">Chargement…</div>
        )}

        {!loading && history.length === 0 && (
          <div className="text-center py-20">
            <p className="text-zinc-500 text-lg mb-2">Aucun historique disponible</p>
            <p className="text-zinc-600 text-sm">
              Les résultats s'affichent automatiquement après chaque match.
              <br />Lancez <code className="bg-white/5 px-1.5 py-0.5 rounded text-violet-300">python scripts/fetch_results.py</code> pour les mettre à jour.
            </p>
          </div>
        )}

        {!loading && history.length > 0 && (
          <>
            {/* Stats cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
              <div className="bg-black/40 border border-white/10 rounded-xl p-4">
                <p className="text-zinc-500 text-xs mb-1">Paris totaux</p>
                <p className="text-2xl font-bold text-white">{resolved.length}</p>
              </div>
              <div className="bg-black/40 border border-white/10 rounded-xl p-4">
                <p className="text-zinc-500 text-xs mb-1">Taux de réussite</p>
                <p className="text-2xl font-bold text-white">{winRate.toFixed(1)}%</p>
                <p className="text-xs text-zinc-600 mt-0.5">{wins}V · {losses}D{pushes > 0 ? ` · ${pushes}N` : ''}</p>
              </div>
              <div className="bg-black/40 border border-white/10 rounded-xl p-4">
                <p className="text-zinc-500 text-xs mb-1">ROI réel</p>
                <p className={`text-2xl font-bold ${roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
                </p>
                <p className="text-xs text-zinc-600 mt-0.5">par pari (mise fixe)</p>
              </div>
              <div className="bg-black/40 border border-white/10 rounded-xl p-4">
                <p className="text-zinc-500 text-xs mb-1">P&L total</p>
                <p className={`text-2xl font-bold ${totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)} u
                </p>
                <p className="text-xs text-zinc-600 mt-0.5">unités (mise 1u / pari)</p>
              </div>
            </div>

            {/* ROI Chart */}
            {chartData.length >= 2 && (
              <div className="bg-black/40 border border-white/10 rounded-xl p-6 mb-8">
                <h2 className="text-sm font-semibold text-zinc-300 mb-4 uppercase tracking-wider">ROI cumulé</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: '#6b7280', fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fill: '#6b7280', fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 4" />
                    <Line
                      type="monotone"
                      dataKey="roi"
                      stroke={roi >= 0 ? '#34d399' : '#f87171'}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: roi >= 0 ? '#34d399' : '#f87171' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Bankroll Simulation */}
            {bankrollData.length >= 2 && (
              <div className="bg-black/40 border border-white/10 rounded-xl p-6 mb-8">
                <h2 className="text-sm font-semibold text-zinc-300 mb-1 uppercase tracking-wider">
                  Simulation de bankroll
                </h2>
                <p className="text-zinc-600 text-xs mb-4">
                  Capital de départ : 1 000 € — Mise fixe : 10 € par pari (1%)
                </p>

                {/* Bankroll stats */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
                  <div className="bg-white/5 rounded-lg px-3 py-2.5">
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider mb-0.5">Capital initial</p>
                    <p className="text-white font-bold text-lg">1 000 €</p>
                  </div>
                  <div className="bg-white/5 rounded-lg px-3 py-2.5">
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider mb-0.5">Capital final</p>
                    <p className={`font-bold text-lg ${finalBankroll >= STARTING_BANKROLL ? 'text-emerald-400' : 'text-red-400'}`}>
                      {finalBankroll.toLocaleString('fr-FR')} €
                    </p>
                  </div>
                  <div className="bg-white/5 rounded-lg px-3 py-2.5">
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider mb-0.5">Profit net</p>
                    <p className={`font-bold text-lg ${totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {totalProfit >= 0 ? '+' : ''}{totalProfit.toLocaleString('fr-FR')} €
                    </p>
                  </div>
                  <div className="bg-white/5 rounded-lg px-3 py-2.5">
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider mb-0.5">Rendement</p>
                    <p className={`font-bold text-lg ${bankrollROI >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {bankrollROI >= 0 ? '+' : ''}{bankrollROI.toFixed(0)}%
                    </p>
                    <p className="text-zinc-600 text-[10px]">Drawdown max : {maxDrawdown.toFixed(1)}%</p>
                  </div>
                </div>

                {/* Bankroll chart */}
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={bankrollData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="bankrollGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#34d399" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: '#6b7280', fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fill: '#6b7280', fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={v => `${(v / 1000).toFixed(1)}k€`}
                    />
                    <Tooltip content={<BankrollTooltip />} />
                    <ReferenceLine y={STARTING_BANKROLL} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" label={{ value: 'Départ', fill: '#6b7280', fontSize: 10 }} />
                    <Area
                      type="monotone"
                      dataKey="bankroll"
                      stroke="#34d399"
                      strokeWidth={2}
                      fill="url(#bankrollGrad)"
                      dot={false}
                      activeDot={{ r: 4, fill: '#34d399' }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Filters */}
            <div className="flex flex-wrap gap-2 mb-4">
              {/* Result filter */}
              <div className="flex rounded-lg overflow-hidden border border-white/10 text-xs">
                {(['all', 'won', 'lost'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-3 py-1.5 transition ${
                      filter === f
                        ? 'bg-violet-600 text-white'
                        : 'bg-black/40 text-zinc-400 hover:text-white'
                    }`}
                  >
                    {f === 'all' ? 'Tous' : f === 'won' ? 'Gagnés' : 'Perdus'}
                  </button>
                ))}
              </div>

              {/* League filter */}
              {leagues.length > 1 && (
                <select
                  value={leagueFilter}
                  onChange={e => setLeagueFilter(e.target.value)}
                  className="bg-black/40 border border-white/10 text-zinc-400 text-xs rounded-lg px-3 py-1.5 focus:outline-none"
                >
                  <option value="all">Toutes les ligues</option>
                  {leagues.map(l => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              )}
            </div>

            {/* Table */}
            <div className="bg-black/40 border border-white/10 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-xs text-zinc-500 uppercase tracking-wider">
                    <th className="text-left px-4 py-3 font-medium">Date</th>
                    <th className="text-left px-4 py-3 font-medium">Match</th>
                    <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">Ligue</th>
                    <th className="text-left px-4 py-3 font-medium">Pari</th>
                    <th className="text-right px-4 py-3 font-medium hidden md:table-cell">Prob.</th>
                    <th className="text-right px-4 py-3 font-medium hidden md:table-cell">Cote</th>
                    <th className="text-center px-4 py-3 font-medium">Score</th>
                    <th className="text-center px-4 py-3 font-medium">Résultat</th>
                    <th className="text-right px-4 py-3 font-medium">P&L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filtered.map((h, i) => (
                    <tr key={h.id ?? i} className="hover:bg-white/5 transition">
                      <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">
                        {formatDate(h.date)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-white font-medium">{h.home_team}</span>
                        <span className="text-zinc-600 mx-1">vs</span>
                        <span className="text-white font-medium">{h.away_team}</span>
                      </td>
                      <td className="px-4 py-3 text-zinc-500 text-xs hidden sm:table-cell">{h.league}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span className="text-zinc-300 text-xs">{formatBet(h.recommended_bet)}</span>
                          {h.confidence_badge && (
                            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${BADGE_COLORS[h.confidence_badge] ?? 'text-zinc-500 bg-white/5 border-white/10'}`}>
                              {h.confidence_badge}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-500 text-xs hidden md:table-cell">
                        {formatProb(h.model_prob)}
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-300 text-xs hidden md:table-cell">
                        {h.odds != null ? h.odds.toFixed(2) : '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {h.resolved && h.home_score != null && h.away_score != null ? (
                          <span className="font-mono text-white text-xs">
                            {h.home_score} – {h.away_score}
                          </span>
                        ) : (
                          <span className="text-zinc-600 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {!h.resolved ? (
                          <span className="text-zinc-600 text-xs">En attente</span>
                        ) : h.won === true ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
                            ✓ Gagné
                          </span>
                        ) : h.won === false ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-semibold">
                            ✗ Perdu
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-semibold">
                            ~ Remb.
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {h.pnl != null ? (
                          <span className={`font-mono text-xs font-semibold ${h.pnl > 0 ? 'text-emerald-400' : h.pnl < 0 ? 'text-red-400' : 'text-yellow-400'}`}>
                            {h.pnl > 0 ? '+' : ''}{h.pnl.toFixed(2)}u
                          </span>
                        ) : (
                          <span className="text-zinc-600 text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-zinc-600 text-sm">
                        Aucun résultat pour ce filtre
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Script tip */}
            <p className="text-center text-zinc-700 text-xs mt-6">
              Mise à jour automatique via{' '}
              <code className="bg-white/5 px-1.5 py-0.5 rounded text-zinc-500">python scripts/fetch_results.py</code>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
