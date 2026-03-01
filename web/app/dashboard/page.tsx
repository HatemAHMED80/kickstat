/* eslint-disable @next/next/no-img-element */
'use client';

import { useState, useEffect } from 'react';
import NavBar from '../components/NavBar';
import { mockPredictions } from './mock-data';

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
function formatBet(bet: string, home: string, away: string): { label: string; desc: string } {
  const bets: Record<string, { label: string; desc: string }> = {
    home:    { label: `Victoire ${home}`, desc: `${home} gagne le match` },
    away:    { label: `Victoire ${away}`, desc: `${away} gagne le match` },
    draw:    { label: 'Match nul', desc: 'Les deux equipes font match nul' },
    ah_home: { label: `Handicap ${home} (-1.5)`, desc: `${home} gagne avec 2 buts d'ecart ou plus` },
    ah_away: { label: `Handicap ${away} (+1.5)`, desc: `${away} gagne, fait nul, ou perd par 1 but max` },
    over15:  { label: '+1.5 buts', desc: '2 buts ou plus dans le match' },
    under15: { label: '-1.5 buts', desc: '0 ou 1 but dans le match' },
    over25:  { label: '+2.5 buts', desc: '3 buts ou plus dans le match' },
    under25: { label: '-2.5 buts', desc: '0, 1 ou 2 buts dans le match' },
    over35:  { label: '+3.5 buts', desc: '4 buts ou plus dans le match' },
    under35: { label: '-3.5 buts', desc: '0 a 3 buts dans le match' },
  };
  return bets[bet] ?? { label: bet, desc: '' };
}

function formatMarket(market: string | undefined, home?: string, away?: string): string {
  if (!market) return '';
  if (market === 'home') return `Victoire ${home || 'dom.'}`;
  if (market === 'away') return `Victoire ${away || 'ext.'}`;
  if (market === 'ah_home') return `Handicap ${home || 'dom.'} (-1.5)`;
  if (market === 'ah_away') return `Handicap ${away || 'ext.'} (+1.5)`;
  const map: Record<string, string> = {
    draw: 'Match nul',
    over15: '+1.5 buts', under15: '-1.5 buts', over25: '+2.5 buts', under25: '-2.5 buts',
    over35: '+3.5 buts', under35: '-3.5 buts',
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
  // Fallback: derive prob from edge + odds (edge = (prob*odds - 1)*100)
  const edge = p.edge?.[b];
  const odds = p.best_odds?.[b];
  if (edge != null && odds != null && odds > 1) {
    return (edge / 100 + 1) / odds;
  }
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
  const [selectedLeague, setSelectedLeague] = useState('all');
  const [selectedType, setSelectedType] = useState<'all' | 'simple' | 'combine'>('all');
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [combos, setCombos] = useState<Combo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // TODO: réactiver l'auth avant la prod

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

  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      <NavBar />

      {/* Header */}
      <div className="border-b border-white/5">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 text-center">
          <div className="flex items-center justify-center gap-3 mb-1">
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
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-center gap-3">
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
                  <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3 text-center">
                    Combines ({combos.length})
                  </h2>
                )}
                <div className="space-y-3">
                  {combos.map(c => <ComboRow key={c.combo_id} combo={c} />)}
                </div>
              </div>
            )}

            {/* Matches without bets */}
            {selectedType !== 'combine' && noBets.length > 0 && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-zinc-600 uppercase tracking-wider mb-3 text-center">
                  Sans pari ({noBets.filter(p => selectedLeague === 'all' || p.league === selectedLeague).length})
                </h2>
                <div className="space-y-1">
                  {noBets
                    .filter(p => selectedLeague === 'all' || p.league === selectedLeague)
                    .map(p => (
                      <div key={p.match_id} className="rounded-lg bg-white/[0.02] text-zinc-600 px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-2 text-sm">
                          {p.home_crest && <img src={p.home_crest} alt="" className="w-4 h-4 shrink-0" />}
                          <span>{p.home_team}</span>
                          <span className="text-zinc-700 text-xs">vs</span>
                          {p.away_crest && <img src={p.away_crest} alt="" className="w-4 h-4 shrink-0" />}
                          <span>{p.away_team}</span>
                        </div>
                        <div className="text-[10px] text-zinc-700 font-mono mt-1">
                          {new Date(p.kickoff).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })} · Edge insuffisant
                        </div>
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
      <button onClick={onToggle} className="w-full px-5 py-4 space-y-3">
        {/* Top: ligue+heure gauche — safe+proba+edge droite */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-600 font-mono">
            {p.league} · {new Date(p.kickoff).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
          </span>
          <div className="flex items-center gap-2">
            {badge && (
              <span className={`px-1.5 py-0.5 rounded-full border text-[9px] font-bold ${badge.cls}`}>
                {badge.icon} {badge.label}
              </span>
            )}
            {prob != null && (
              <span className="text-[10px] text-zinc-500 font-mono">Proba {(prob * 100).toFixed(0)}%</span>
            )}
            {edge != null && (
              <span className="text-[10px] text-emerald-500/70 font-mono">Edge +{edge.toFixed(1)}%</span>
            )}
          </div>
        </div>

        {/* Equipes centrées */}
        <div className="flex items-center justify-center gap-3">
          <div className="flex items-center gap-2 flex-1 justify-end min-w-0">
            <span className="text-base font-semibold text-white truncate">{p.home_team}</span>
            {p.home_crest && <img src={p.home_crest} alt="" className="w-7 h-7 shrink-0" />}
          </div>
          <span className="text-zinc-600 text-xs shrink-0">vs</span>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {p.away_crest && <img src={p.away_crest} alt="" className="w-7 h-7 shrink-0" />}
            <span className="text-base font-semibold text-white truncate">{p.away_team}</span>
          </div>
        </div>

        {/* 2 blocs : pari + cote */}
        <div className="flex gap-2">
          <div className="flex-1 rounded-lg bg-violet-500/15 border border-violet-500/25 px-3 py-2.5 text-center">
            <div className="text-[10px] text-violet-400/60 font-mono uppercase tracking-wider mb-0.5">Pari conseille</div>
            <div className="text-base font-bold text-violet-200">{formatBet(bet, p.home_team, p.away_team).label}</div>
            <div className="text-[10px] text-zinc-500 mt-0.5">{formatBet(bet, p.home_team, p.away_team).desc}</div>
          </div>
          <div className="w-24 shrink-0 rounded-lg bg-yellow-500/10 border border-yellow-500/20 px-3 py-2.5 text-center">
            <div className="text-[10px] text-yellow-400/60 font-mono uppercase tracking-wider mb-0.5">Cote</div>
            <div className="text-xl font-black text-yellow-400 font-mono">{odds != null ? odds.toFixed(2) : '—'}</div>
          </div>
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-5 pb-5 pt-3 border-t border-white/5 space-y-4">

          {/* Stats clés — 3 blocs colorés centrés */}
          <div className="flex justify-center gap-2">
            {prob != null && (
              <div className="flex-1 max-w-[120px] rounded-lg bg-blue-500/10 border border-blue-500/20 px-3 py-2 text-center">
                <div className="text-[10px] text-blue-400/60 font-mono uppercase tracking-wider">Probabilite</div>
                <div className="text-lg font-bold text-blue-300">{(prob * 100).toFixed(0)}%</div>
              </div>
            )}
            {p.kelly_stake > 0 && (
              <div className="flex-1 max-w-[120px] rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-center">
                <div className="text-[10px] text-emerald-400/60 font-mono uppercase tracking-wider">Kelly</div>
                <div className="text-lg font-bold text-emerald-300">{p.kelly_stake.toFixed(1)}%</div>
                <div className="text-[9px] text-zinc-600">Mise optimale</div>
              </div>
            )}
            {odds != null && prob != null && (
              <div className="flex-1 max-w-[120px] rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-center">
                <div className="text-[10px] text-amber-400/60 font-mono uppercase tracking-wider">EV</div>
                <div className="text-lg font-bold text-amber-300">{(prob * odds - 1).toFixed(2)}</div>
                <div className="text-[9px] text-zinc-600">{(prob * odds - 1) > 0 ? `+${((prob * odds - 1) * 100).toFixed(0)} cts / 1€ mise` : 'Gain espere / mise'}</div>
              </div>
            )}
          </div>

          {/* Over / Under 2.5 — blocs séparés */}
          {p.over_under && (
            <div className="text-center">
              <div className="text-[10px] text-zinc-600 font-mono uppercase tracking-wider mb-1.5">Buts dans le match</div>
              <div className="flex justify-center gap-2">
                <div className="rounded-md bg-white/[0.03] border border-white/5 px-3 py-1.5 text-center min-w-[100px]">
                  <div className="text-xs text-zinc-400">+ de 2.5 buts</div>
                  <div className="text-sm font-bold text-white">{(p.over_under.over_25 * 100).toFixed(0)}%</div>
                </div>
                <div className="rounded-md bg-white/[0.03] border border-white/5 px-3 py-1.5 text-center min-w-[100px]">
                  <div className="text-xs text-zinc-400">- de 2.5 buts</div>
                  <div className="text-sm font-bold text-white">{(p.over_under.under_25 * 100).toFixed(0)}%</div>
                </div>
              </div>
            </div>
          )}

          {/* Forme — 5 derniers matchs avec scores */}
          {(p.home_stats?.recent_matches || p.away_stats?.recent_matches) && (
            <div className="text-center">
              <div className="text-[10px] text-zinc-600 font-mono uppercase tracking-wider mb-2">5 derniers matchs</div>
              <div className="space-y-3">
                {p.home_stats?.recent_matches && (
                  <div>
                    <div className="text-[11px] text-zinc-500 font-medium mb-1">{p.home_team}</div>
                    <div className="flex justify-center gap-1.5">
                      {p.home_stats.recent_matches.slice(0, 5).map((m, i) => (
                        <div key={i} className={`rounded-md px-2 py-1 text-center min-w-[48px] border ${
                          m.result === 'win'
                            ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
                            : m.result === 'draw'
                            ? 'bg-yellow-500/10 border-yellow-500/25 text-yellow-400'
                            : 'bg-red-500/10 border-red-500/25 text-red-400'
                        }`}>
                          <div className="text-[10px] font-bold">{m.score}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {p.away_stats?.recent_matches && (
                  <div>
                    <div className="text-[11px] text-zinc-500 font-medium mb-1">{p.away_team}</div>
                    <div className="flex justify-center gap-1.5">
                      {p.away_stats.recent_matches.slice(0, 5).map((m, i) => (
                        <div key={i} className={`rounded-md px-2 py-1 text-center min-w-[48px] border ${
                          m.result === 'win'
                            ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
                            : m.result === 'draw'
                            ? 'bg-yellow-500/10 border-yellow-500/25 text-yellow-400'
                            : 'bg-red-500/10 border-red-500/25 text-red-400'
                        }`}>
                          <div className="text-[10px] font-bold">{m.score}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* H2H */}
          {p.h2h_stats && (
            <div className="text-center">
              <div className="text-[10px] text-zinc-600 font-mono uppercase tracking-wider mb-1">Confrontations directes ({p.h2h_stats.total_matches} matchs)</div>
              <div className="flex justify-center gap-3 text-xs">
                <span className="text-emerald-400">{p.h2h_stats.home_wins}V</span>
                <span className="text-yellow-400">{p.h2h_stats.draws}N</span>
                <span className="text-red-400">{p.h2h_stats.away_wins}D</span>
                <span className="text-zinc-500">Moy {p.h2h_stats.avg_goals.toFixed(1)} buts</span>
              </div>
            </div>
          )}

          {/* Scores probables */}
          {p.correct_score && (
            <div className="text-center">
              <div className="text-[10px] text-zinc-600 font-mono uppercase tracking-wider mb-1.5">Scores les plus probables</div>
              <div className="flex justify-center gap-2">
                {Object.entries(p.correct_score).slice(0, 3).map(([score, pr]) => (
                  <div key={score} className="rounded-md bg-white/[0.03] border border-white/5 px-3 py-1.5 text-center">
                    <div className="text-sm font-bold text-white font-mono">{score}</div>
                    <div className="text-[10px] text-zinc-500">{(pr * 100).toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}
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
    <div className="rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/10 transition overflow-hidden px-5 py-4 space-y-3">
      {/* Top: type gauche — badge+proba+edge droite */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-zinc-600 font-mono">
          {c.type === 'same_match' ? 'Same match' : `Combine ${legs} selections`}
        </span>
        <div className="flex items-center gap-2">
          {badge && (
            <span className={`px-1.5 py-0.5 rounded-full border text-[9px] font-bold ${badge.cls}`}>
              {badge.icon} {badge.label}
            </span>
          )}
          <span className="text-[10px] text-zinc-500 font-mono">Proba {(c.prob * 100).toFixed(0)}%</span>
          <span className="text-[10px] text-emerald-500/70 font-mono">Edge +{c.edge.toFixed(1)}%</span>
        </div>
      </div>

      {/* Legs — pari gauche + cote droite */}
      <div className="space-y-1.5">
        {c.matches.map((leg, i) => (
          <div key={i} className="flex gap-2">
            <div className="flex-1 rounded-lg bg-cyan-500/10 border border-cyan-500/20 px-3 py-2 text-center">
              <div className="text-[10px] text-zinc-500">{leg.home_team} vs {leg.away_team}</div>
              <div className="text-sm font-semibold text-cyan-200">{formatMarket(leg.market, leg.home_team, leg.away_team)}</div>
            </div>
            <div className="w-20 shrink-0 rounded-lg bg-orange-500/10 border border-orange-500/20 px-2 py-2 text-center flex flex-col justify-center">
              <div className="text-[9px] text-orange-400/60 font-mono uppercase">Cote</div>
              <div className="text-base font-black text-orange-300 font-mono">{leg.odds != null ? leg.odds.toFixed(2) : '—'}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Total : recap + cote combinée */}
      <div className="flex gap-2 pt-1 border-t border-white/5">
        <div className="flex-1 rounded-lg bg-cyan-500/15 border border-cyan-500/25 px-3 py-2.5 text-center">
          <div className="text-[10px] text-cyan-400/60 font-mono uppercase tracking-wider mb-0.5">Total combine</div>
          <div className="text-sm font-bold text-cyan-200">{legs} selections</div>
        </div>
        <div className="w-20 shrink-0 rounded-lg bg-orange-500/15 border border-orange-500/25 px-2 py-2.5 text-center">
          <div className="text-[9px] text-orange-400/60 font-mono uppercase">Cote</div>
          <div className="text-xl font-black text-orange-300 font-mono">{c.combined_odds.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}
