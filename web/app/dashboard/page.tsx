/* eslint-disable @next/next/no-img-element */
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import NavBar from '../components/NavBar';
import { mockPredictions } from './mock-data';
import { useAuth } from '../contexts/auth-context';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Prediction {
  match_id: string;
  league: string;
  home_team: string;
  away_team: string;
  kickoff: string;
  model_probs: { home: number; draw: number; away: number };
  best_odds: { [key: string]: number };
  edge: { [key: string]: number };
  recommended_bet: string | null;
  kelly_stake: number;
  confidence_badge?: string | null;
  over_under?: { over_25: number; under_25: number } | null;
  over_under_edge?: { over_25: number; under_25: number } | null;
  over_under_15?: { over_15: number; under_15: number } | null;
  over_under_35?: { over_35: number; under_35: number } | null;
  home_stats?: { recent_matches: Array<{ result: 'win' | 'draw' | 'loss'; opponent: string; score: string; date: string }> };
  away_stats?: { recent_matches: Array<{ result: 'win' | 'draw' | 'loss'; opponent: string; score: string; date: string }> };
  h2h_stats?: { total_matches: number; home_wins: number; draws: number; away_wins: number; avg_goals: number };
  correct_score?: { [key: string]: number } | null;
  home_crest?: string;
  away_crest?: string;
}

interface ComboLeg {
  home_team: string;
  away_team: string;
  league: string;
  market?: string;
  prob?: number;
  odds?: number;
}

interface Combo {
  type: 'same_match' | 'cross_match';
  combo_id: string;
  label: string;
  matches: ComboLeg[];
  n_legs?: number;
  prob: number;
  combined_odds: number;
  edge: number;
  kelly_stake: number;
  confidence: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatBet(bet: string, home: string, away: string): string {
  if (bet === 'home') return `1 — ${home}`;
  if (bet === 'away') return `2 — ${away}`;
  if (bet === 'ah_home') return `AH ${home}`;
  if (bet === 'ah_away') return `AH ${away}`;
  const map: Record<string, string> = {
    draw: 'Nul', over15: '+1.5 buts', under15: '-1.5 buts',
    over25: '+2.5 buts', under25: '-2.5 buts', over35: '+3.5 buts', under35: '-3.5 buts',
  };
  return map[bet] ?? bet;
}

function formatMarket(market: string | undefined): string {
  if (!market) return '';
  const map: Record<string, string> = {
    home: 'Victoire dom.', draw: 'Nul', away: 'Victoire ext.',
    over15: '+1.5 buts', under15: '-1.5 buts', over25: '+2.5 buts', under25: '-2.5 buts',
    over35: '+3.5 buts', under35: '-3.5 buts', ah_home: 'AH Dom.', ah_away: 'AH Ext.',
  };
  return map[market] ?? market;
}

function getBetOdds(p: Prediction): number | null {
  return p.recommended_bet ? (p.best_odds?.[p.recommended_bet] ?? null) : null;
}

function getBetEdge(p: Prediction): number | null {
  return p.recommended_bet ? (p.edge?.[p.recommended_bet] ?? null) : null;
}

function getBetProb(p: Prediction): number | null {
  const b = p.recommended_bet;
  if (!b) return null;
  if (['home', 'draw', 'away'].includes(b)) return p.model_probs[b as keyof typeof p.model_probs] ?? null;
  if (b === 'over25') return p.over_under?.over_25 ?? null;
  if (b === 'under25') return p.over_under?.under_25 ?? null;
  if (b === 'over15') return (p as any).over_under_15?.over_15 ?? null;
  if (b === 'under15') return (p as any).over_under_15?.under_15 ?? null;
  if (b === 'over35') return (p as any).over_under_35?.over_35 ?? null;
  if (b === 'under35') return (p as any).over_under_35?.under_35 ?? null;
  return null;
}

const BADGE: Record<string, { icon: string; label: string; cls: string }> = {
  ULTRA_SAFE:  { icon: '🏆', label: 'ULTRA SAFE',  cls: 'text-yellow-300 bg-yellow-400/10 border-yellow-400/40' },
  HIGH_SAFE:   { icon: '🛡️', label: 'HIGH SAFE',   cls: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/40' },
  SAFE:        { icon: '✅', label: 'SAFE',         cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/40' },
  VALUE:       { icon: '💎', label: 'VALUE',        cls: 'text-violet-400 bg-violet-500/10 border-violet-500/40' },
  RISKY:       { icon: '⚠️', label: 'RISQUE',       cls: 'text-orange-400 bg-orange-500/10 border-orange-500/40' },
  ULTRA_RISKY: { icon: '💀', label: 'ULTRA RISQUE', cls: 'text-red-400 bg-red-500/10 border-red-500/40' },
};

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const { session, loading: authLoading } = useAuth();
  const router = useRouter();
  const [selectedLeague, setSelectedLeague] = useState('all');
  const [selectedType, setSelectedType] = useState<'all' | 'simple' | 'combine'>('all');
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [combos, setCombos] = useState<Combo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !session) router.push('/login');
  }, [authLoading, session, router]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await fetch('/predictions.json');
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        if (Array.isArray(data)) {
          setPredictions(data);
        } else {
          setPredictions(data.predictions || []);
          setCombos(data.combos || []);
        }
      } catch {
        setError('Impossible de charger les predictions.');
        // @ts-ignore
        setPredictions(mockPredictions);
      }
      setLoading(false);
    })();
  }, []);

  const bets = predictions.filter(p => p.recommended_bet);
  const noBets = predictions.filter(p => !p.recommended_bet);

  const filteredBets = bets.filter(p =>
    selectedLeague === 'all' || p.league === selectedLeague
  );

  const leagues = Array.from(new Set(predictions.map(p => p.league)));

  if (authLoading || !session) {
    return (
      <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      <NavBar />

      {/* Header */}
      <div className="border-b border-white/5">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold">Paris du jour</h1>
            <span className="px-2.5 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-[10px] font-mono uppercase tracking-widest animate-pulse">
              Live
            </span>
          </div>
          <p className="text-zinc-600 font-mono text-xs">
            {new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            {' · '}{predictions.length} matchs · {bets.length} paris
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="border-b border-white/5">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center gap-3">
          <select
            value={selectedLeague}
            onChange={e => setSelectedLeague(e.target.value)}
            className="px-3 py-1.5 text-xs border border-white/10 rounded-lg bg-[#18181b] text-zinc-300 font-mono"
          >
            <option value="all">Toutes les ligues</option>
            {leagues.map(l => <option key={l} value={l}>{l}</option>)}
          </select>

          <div className="flex rounded-lg overflow-hidden border border-white/10 text-xs">
            {(['all', 'simple', 'combine'] as const).map(t => (
              <button
                key={t}
                onClick={() => setSelectedType(t)}
                className={`px-3 py-1.5 transition font-medium ${
                  selectedType === t
                    ? 'bg-violet-600 text-white'
                    : 'bg-transparent text-zinc-500 hover:text-white'
                }`}
              >
                {t === 'all' ? 'Tous' : t === 'simple' ? 'Simples' : 'Combines'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
        {loading && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-violet-400 border-t-transparent rounded-full animate-spin mb-3" />
            <p className="text-zinc-500 text-sm">Chargement...</p>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-6 text-sm text-red-300">
            {error}
          </div>
        )}

        {!loading && (
          <>
            {/* Single bets */}
            {selectedType !== 'combine' && (
              <div className="space-y-2 mb-8">
                {filteredBets.length === 0 && (
                  <p className="text-center text-zinc-600 py-8 text-sm">Aucun pari recommande</p>
                )}
                {filteredBets.map(p => (
                  <BetRow
                    key={p.match_id}
                    prediction={p}
                    expanded={expandedId === p.match_id}
                    onToggle={() => setExpandedId(expandedId === p.match_id ? null : p.match_id)}
                  />
                ))}
              </div>
            )}

            {/* Combos */}
            {selectedType !== 'simple' && combos.length > 0 && (
              <div>
                {selectedType === 'all' && (
                  <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                    Combines ({combos.length})
                  </h2>
                )}
                <div className="space-y-2">
                  {combos.map(c => <ComboRow key={c.combo_id} combo={c} />)}
                </div>
              </div>
            )}

            {/* Matches without bets */}
            {selectedType !== 'combine' && noBets.length > 0 && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-zinc-600 uppercase tracking-wider mb-3">
                  Sans pari ({noBets.filter(p => selectedLeague === 'all' || p.league === selectedLeague).length})
                </h2>
                <div className="space-y-1">
                  {noBets
                    .filter(p => selectedLeague === 'all' || p.league === selectedLeague)
                    .map(p => (
                      <div key={p.match_id} className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-white/[0.02] text-zinc-600 text-sm">
                        <span className="text-xs font-mono w-12 shrink-0">
                          {new Date(p.kickoff).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <div className="truncate flex items-center gap-1.5">
                          {p.home_crest && <img src={p.home_crest} alt="" className="w-3.5 h-3.5 shrink-0" />}
                          {p.home_team} vs
                          {p.away_crest && <img src={p.away_crest} alt="" className="w-3.5 h-3.5 shrink-0" />}
                          {p.away_team}
                        </div>
                        <span className="ml-auto text-[10px] whitespace-nowrap">Edge insuffisant</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer disclaimer */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-8">
        <p className="text-[10px] text-zinc-700 text-center leading-relaxed">
          Predictions statistiques, aucun resultat garanti. 18+ · Jouez responsablement · Joueurs Info Service 09 74 75 13 13
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BetRow — compact expandable row
// ---------------------------------------------------------------------------
function BetRow({ prediction: p, expanded, onToggle }: {
  prediction: Prediction;
  expanded: boolean;
  onToggle: () => void;
}) {
  const bet = p.recommended_bet!;
  const odds = getBetOdds(p);
  const edge = getBetEdge(p);
  const prob = getBetProb(p);
  const badge = p.confidence_badge ? BADGE[p.confidence_badge] : null;

  return (
    <div className={`rounded-xl border transition-all overflow-hidden ${
      expanded ? 'border-violet-500/30 bg-white/[0.03]' : 'border-white/5 bg-white/[0.02] hover:border-white/10'
    }`}>
      <button onClick={onToggle} className="w-full text-left px-5 py-4 space-y-4">
        {/* Top: league + time + badge */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-zinc-500 font-mono">
            {p.league} · {new Date(p.kickoff).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
          </span>
          <div className="flex items-center gap-2">
            {badge && (
              <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${badge.cls}`}>
                {badge.icon} {badge.label}
              </span>
            )}
            <span className={`text-zinc-600 text-xs transition-transform ${expanded ? 'rotate-90' : ''}`}>&#9654;</span>
          </div>
        </div>

        {/* Teams centered */}
        <div className="flex items-center justify-center gap-4">
          <div className="flex items-center gap-2.5 flex-1 justify-end min-w-0">
            <span className="text-[15px] font-semibold text-white truncate">{p.home_team}</span>
            {p.home_crest && <img src={p.home_crest} alt="" className="w-7 h-7 shrink-0" />}
          </div>
          <span className="text-xs text-zinc-600 font-medium shrink-0">vs</span>
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            {p.away_crest && <img src={p.away_crest} alt="" className="w-7 h-7 shrink-0" />}
            <span className="text-[15px] font-semibold text-white truncate">{p.away_team}</span>
          </div>
        </div>

        {/* Recommended bet — highlighted block */}
        <div className="rounded-lg bg-violet-500/10 border border-violet-500/20 px-3.5 py-2.5">
          <div className="text-sm font-bold text-violet-300 mb-1.5">
            ✦ {formatBet(bet, p.home_team, p.away_team)}
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            {odds != null && (
              <span><span className="text-zinc-500">Cote</span> <span className="text-yellow-400 font-bold text-sm">{odds.toFixed(2)}</span></span>
            )}
            {prob != null && (
              <span><span className="text-zinc-500">Proba</span> <span className="text-white font-semibold">{(prob * 100).toFixed(0)}%</span></span>
            )}
            {edge != null && (
              <span><span className="text-zinc-500">Edge</span> <span className="text-emerald-400 font-semibold">+{edge.toFixed(1)}%</span></span>
            )}
          </div>
        </div>

        {/* 1X2 probabilities — subtle */}
        <div className="flex justify-between text-[10px] font-mono text-zinc-600 px-1">
          <span>Dom {(p.model_probs.home * 100).toFixed(0)}%</span>
          <span>Nul {(p.model_probs.draw * 100).toFixed(0)}%</span>
          <span>Ext {(p.model_probs.away * 100).toFixed(0)}%</span>
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-5 pb-4 pt-1 border-t border-white/5 space-y-3">
          {/* Over/Under */}
          {p.over_under && (
            <div className="flex gap-4 text-xs">
              <span className="text-zinc-500">O/U 2.5 :</span>
              <span className="text-zinc-300">+2.5 {(p.over_under.over_25 * 100).toFixed(0)}%</span>
              <span className="text-zinc-300">-2.5 {(p.over_under.under_25 * 100).toFixed(0)}%</span>
            </div>
          )}

          {/* Form */}
          {(p.home_stats?.recent_matches || p.away_stats?.recent_matches) && (
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-6 text-xs">
              {p.home_stats?.recent_matches && (
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500 w-20 truncate">{p.home_team}</span>
                  <div className="flex gap-1">
                    {p.home_stats.recent_matches.slice(0, 5).map((m, i) => (
                      <div key={i} className={`w-2.5 h-2.5 rounded-full ${
                        m.result === 'win' ? 'bg-emerald-400' : m.result === 'draw' ? 'bg-yellow-400' : 'bg-red-500'
                      }`} />
                    ))}
                  </div>
                </div>
              )}
              {p.away_stats?.recent_matches && (
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500 w-20 truncate">{p.away_team}</span>
                  <div className="flex gap-1">
                    {p.away_stats.recent_matches.slice(0, 5).map((m, i) => (
                      <div key={i} className={`w-2.5 h-2.5 rounded-full ${
                        m.result === 'win' ? 'bg-emerald-400' : m.result === 'draw' ? 'bg-yellow-400' : 'bg-red-500'
                      }`} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* H2H */}
          {p.h2h_stats && (
            <div className="text-xs text-zinc-500">
              H2H ({p.h2h_stats.total_matches}) : {p.h2h_stats.home_wins}V · {p.h2h_stats.draws}N · {p.h2h_stats.away_wins}D · Moy {p.h2h_stats.avg_goals.toFixed(1)} buts
            </div>
          )}

          {/* Correct scores */}
          {p.correct_score && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-zinc-500">Scores :</span>
              {Object.entries(p.correct_score).slice(0, 3).map(([score, pr]) => (
                <span key={score} className="px-1.5 py-0.5 rounded bg-white/5 text-zinc-400 font-mono text-[10px]">
                  {score} {(pr * 100).toFixed(0)}%
                </span>
              ))}
            </div>
          )}

          {/* Kelly + prob */}
          <div className="flex gap-4 text-[10px] text-zinc-600 font-mono pt-1 border-t border-white/5">
            {prob != null && <span>Prob : {(prob * 100).toFixed(0)}%</span>}
            {p.kelly_stake > 0 && <span>Kelly : {p.kelly_stake.toFixed(1)}%</span>}
            {odds != null && prob != null && <span>EV : {(prob * odds - 1).toFixed(2)}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ComboRow — compact combo display
// ---------------------------------------------------------------------------
function ComboRow({ combo: c }: { combo: Combo }) {
  const badge = BADGE[c.confidence];
  const legs = c.n_legs || c.matches.length;

  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/10 transition overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-2">
        {badge && (
          <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${badge.cls}`}>
            {badge.icon} {badge.label}
          </span>
        )}
        <span className="text-[10px] text-zinc-500 font-mono">
          {c.type === 'same_match' ? 'Same match' : `${legs} selections`}
        </span>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-emerald-400 text-[10px] font-mono">+{c.edge.toFixed(1)}%</span>
          <span className="text-lg font-bold text-yellow-400 font-mono">{c.combined_odds.toFixed(2)}</span>
        </div>
      </div>

      {/* Legs */}
      <div className="px-4 pb-3 space-y-1.5">
        {c.matches.map((leg, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-4 h-4 rounded-full bg-violet-500/15 border border-violet-500/25 flex items-center justify-center text-violet-400 text-[10px] font-bold shrink-0">
              {i + 1}
            </span>
            <span className="text-zinc-500 truncate">{leg.home_team} vs {leg.away_team}</span>
            <span className="text-violet-400 font-medium shrink-0">{formatMarket(leg.market)}</span>
            {leg.odds && <span className="text-zinc-600 font-mono shrink-0">{leg.odds.toFixed(2)}</span>}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-white/5 flex gap-4 text-[10px] text-zinc-500 font-mono">
        <span>Prob {(c.prob * 100).toFixed(0)}%</span>
        <span>Kelly {c.kelly_stake.toFixed(1)}%</span>
      </div>
    </div>
  );
}
