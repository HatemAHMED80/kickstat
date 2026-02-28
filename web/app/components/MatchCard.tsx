'use client';

import { useState } from 'react';

interface TeamRecentMatch {
  date: string;
  opponent: string;
  score: string;
  result: 'win' | 'draw' | 'loss';
  home_away: string;
  clean_sheet: boolean;
}

interface TeamStats {
  ppg: number;
  goals_scored_avg: number;
  goals_conceded_avg: number;
  shots_per_game: number;
  shots_on_target_per_game: number;
  shot_accuracy: number;
  corners_per_game: number;
  dominance_score: number;
  recent_form: string;
  recent_matches: TeamRecentMatch[];
}

interface H2HStats {
  total_matches: number;
  home_wins: number;
  draws: number;
  away_wins: number;
  avg_goals: number;
  over_25_rate: number;
  recent_results: Array<{ date: string; score: string; result: string }>;
}

interface BanditRecommendation {
  market: string;
  confidence: number;
  segment: string;
  scores: { [key: string]: number };
}

interface MatchPrediction {
  match_id: string;
  league: string;
  league_slug?: string;
  home_team: string;
  away_team: string;
  kickoff: string;
  model_probs: { home: number; draw: number; away: number };
  best_odds?: { home: number; draw: number; away: number };
  edge?: { home: number; draw: number; away: number };
  home_stats?: TeamStats;
  away_stats?: TeamStats;
  h2h_stats?: H2HStats;
  over_under?: { over_25: number; under_25: number } | null;
  over_under_odds?: { over_25: number; under_25: number } | null;
  over_under_edge?: { over_25: number; under_25: number } | null;
  btts?: { yes: number; no: number } | null;
  correct_score?: { [key: string]: number } | null;
  quality_score?: number | null;
  confidence_badge?: string | null;
  recommended_bet?: string | null;
  kelly_stake?: number;
  segment?: string;
  is_european?: boolean;
  prediction_source?: string;
  bandit_recommendation?: BanditRecommendation | null;
}

interface AccordionProps {
  title: string;
  icon: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

// Utility: Get edge color and style
function getEdgeColorClass(edge: number): string {
  if (edge > 15) return 'text-fuchsia-400';
  if (edge > 8) return 'text-violet-400';
  if (edge > 3) return 'text-violet-300';
  return 'text-gray-600';
}

function getEdgeBgClass(edge: number): string {
  if (edge > 15) return 'bg-fuchsia-500/10 border-fuchsia-500/50 shadow-fuchsia-500/20';
  if (edge > 8) return 'bg-violet-500/10 border-violet-500/50 shadow-violet-500/20';
  if (edge > 3) return 'bg-violet-500/5 border-violet-500/30 shadow-violet-500/10';
  return 'bg-white/3 border-white/5';
}

function getEdgeBadge(edge: number): React.ReactNode {
  if (edge > 15) {
    return (
      <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-fuchsia-500/20 border border-fuchsia-500/50 text-fuchsia-400 text-xs font-bold animate-pulse">
        🔥 HOT
      </div>
    );
  }
  if (edge > 8) {
    return (
      <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-violet-500/20 border border-violet-500/50 text-violet-400 text-xs font-bold">
        ⚡ VALUE
      </div>
    );
  }
  return null;
}

// Confidence Badge Component
function getConfidenceBadge(badge: string | null | undefined): React.ReactNode {
  if (!badge) return null;
  const tiers: Record<string, { icon: string; label: string; cls: string }> = {
    ULTRA_SAFE:  { icon: '🏆', label: 'ULTRA SAFE',  cls: 'bg-yellow-400/20 border-yellow-400/60 text-yellow-300' },
    HIGH_SAFE:   { icon: '🛡️', label: 'HIGH SAFE',   cls: 'bg-emerald-400/20 border-emerald-400/60 text-emerald-300' },
    SAFE:        { icon: '✅', label: 'SAFE',         cls: 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' },
    VALUE:       { icon: '💎', label: 'VALUE',        cls: 'bg-violet-500/20 border-violet-500/50 text-violet-400' },
    RISKY:       { icon: '⚠️', label: 'RISQUÉ',       cls: 'bg-orange-500/20 border-orange-500/50 text-orange-400' },
    ULTRA_RISKY: { icon: '💀', label: 'ULTRA RISQUÉ', cls: 'bg-red-600/20 border-red-500/60 text-red-400 animate-pulse' },
  };
  const t = tiers[badge];
  if (!t) return null;
  return (
    <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold ${t.cls}`}>
      {t.icon} {t.label}
    </div>
  );
}

// Extract odds/edge/prob for the recommended_bet market
function getBetOdds(p: MatchPrediction): number | null {
  const b = p.recommended_bet;
  if (!b) return null;
  if (b === 'home') return p.best_odds?.home ?? null;
  if (b === 'draw') return p.best_odds?.draw ?? null;
  if (b === 'away') return p.best_odds?.away ?? null;
  if (b === 'over25') return (p as any).over_under_odds?.over_25 ?? (p.best_odds as any)?.over25 ?? null;
  if (b === 'under25') return (p as any).over_under_odds?.under_25 ?? (p.best_odds as any)?.under25 ?? null;
  if (b === 'over15') return (p as any).over_under_15_odds?.over_15 ?? (p.best_odds as any)?.over15 ?? null;
  if (b === 'under15') return (p as any).over_under_15_odds?.under_15 ?? (p.best_odds as any)?.under15 ?? null;
  if (b === 'over35') return (p as any).over_under_35_odds?.over_35 ?? (p.best_odds as any)?.over35 ?? null;
  if (b === 'under35') return (p as any).over_under_35_odds?.under_35 ?? (p.best_odds as any)?.under35 ?? null;
  if (b === 'btts_yes') return (p.best_odds as any)?.btts_yes ?? null;
  if (b === 'btts_no') return (p.best_odds as any)?.btts_no ?? null;
  if (b === 'spread_home_m15') return (p.best_odds as any)?.spread_home_m15 ?? null;
  if (b === 'spread_away_p15') return (p.best_odds as any)?.spread_away_p15 ?? null;
  if (b === 'spread_home_m25') return (p.best_odds as any)?.spread_home_m25 ?? null;
  if (b === 'spread_away_p25') return (p.best_odds as any)?.spread_away_p25 ?? null;
  return null;
}

function getBetEdge(p: MatchPrediction): number | null {
  const b = p.recommended_bet;
  if (!b) return null;
  if (b === 'home') return p.edge?.home ?? null;
  if (b === 'draw') return p.edge?.draw ?? null;
  if (b === 'away') return p.edge?.away ?? null;
  if (b === 'over25') return p.over_under_edge?.over_25 ?? null;
  if (b === 'under25') return p.over_under_edge?.under_25 ?? null;
  if (b === 'over15') return (p as any).over_under_15_edge?.over_15 ?? null;
  if (b === 'under15') return (p as any).over_under_15_edge?.under_15 ?? null;
  if (b === 'over35') return (p as any).over_under_35_edge?.over_35 ?? null;
  if (b === 'under35') return (p as any).over_under_35_edge?.under_35 ?? null;
  if (b === 'btts_yes') return (p.edge as any)?.btts_yes ?? null;
  if (b === 'btts_no') return (p.edge as any)?.btts_no ?? null;
  if (b === 'spread_home_m15') return (p.edge as any)?.spread_home_m15 ?? null;
  if (b === 'spread_away_p15') return (p.edge as any)?.spread_away_p15 ?? null;
  if (b === 'spread_home_m25') return (p.edge as any)?.spread_home_m25 ?? null;
  if (b === 'spread_away_p25') return (p.edge as any)?.spread_away_p25 ?? null;
  return null;
}

function getBetProb(p: MatchPrediction): number | null {
  const b = p.recommended_bet;
  if (!b) return null;
  if (b === 'home') return p.model_probs.home;
  if (b === 'draw') return p.model_probs.draw;
  if (b === 'away') return p.model_probs.away;
  if (b === 'over25') return p.over_under?.over_25 ?? null;
  if (b === 'under25') return p.over_under?.under_25 ?? null;
  if (b === 'over15') return (p as any).over_under_15?.over_15 ?? null;
  if (b === 'under15') return (p as any).over_under_15?.under_15 ?? null;
  if (b === 'over35') return (p as any).over_under_35?.over_35 ?? null;
  if (b === 'under35') return (p as any).over_under_35?.under_35 ?? null;
  if (b === 'btts_yes') return p.btts?.yes ?? null;
  if (b === 'btts_no') return p.btts?.no ?? null;
  // Double chance: sum of constituent 1X2 probabilities
  if (b === 'dc_1x') return p.model_probs.home + p.model_probs.draw;
  if (b === 'dc_x2') return p.model_probs.draw + p.model_probs.away;
  if (b === 'dc_12') return p.model_probs.home + p.model_probs.away;
  // Draw no bet: home or away win probability, excluding draws
  if (b === 'dnb_home') {
    const s = p.model_probs.home + p.model_probs.away;
    return s > 0 ? p.model_probs.home / s : null;
  }
  if (b === 'dnb_away') {
    const s = p.model_probs.home + p.model_probs.away;
    return s > 0 ? p.model_probs.away / s : null;
  }
  if (b === 'spread_home_m15') return (p as any).spreads?.home_m15 ?? null;
  if (b === 'spread_away_p15') {
    const hm15 = (p as any).spreads?.home_m15;
    return hm15 != null ? 1 - hm15 : null;
  }
  if (b === 'spread_home_m25') return (p as any).spreads?.home_m25 ?? null;
  if (b === 'spread_away_p25') {
    const hm25 = (p as any).spreads?.home_m25;
    return hm25 != null ? 1 - hm25 : null;
  }
  return null;
}

// Returns a plain-French explanation for a bet type
function getBetExplanation(bet: string, homeTeam: string, awayTeam: string): string | null {
  const h = homeTeam;
  const a = awayTeam;
  const map: Record<string, string> = {
    home:            `${h} gagne le match.`,
    draw:            'Les deux équipes finissent à égalité.',
    away:            `${a} gagne le match.`,
    over15:          'Au moins 2 buts dans le match.',
    under15:         '0 ou 1 but dans le match.',
    over25:          'Au moins 3 buts dans le match.',
    under25:         '0, 1 ou 2 buts dans le match.',
    over35:          'Au moins 4 buts dans le match.',
    under35:         '3 buts ou moins dans le match.',
    btts_yes:        `${h} ET ${a} marquent chacun au moins un but.`,
    btts_no:         `${h} ou ${a} ne marque pas.`,
    dc_1x:           `${h} gagne OU nul — perdant si ${a} gagne.`,
    dc_x2:           `Nul OU ${a} gagne — perdant si ${h} gagne.`,
    dc_12:           `${h} ou ${a} gagne — perdant si match nul.`,
    dnb_home:        `${h} gagne → gagné · Nul → remboursé · ${a} gagne → perdu.`,
    dnb_away:        `${a} gagne → gagné · Nul → remboursé · ${h} gagne → perdu.`,
    spread_home_m15: `${h} doit gagner par 2 buts ou plus.`,
    spread_away_p15: `${a} gagne, nul, ou perd d'un seul but.`,
    spread_home_m25: `${h} doit gagner par 3 buts ou plus.`,
    spread_away_p25: `${a} gagne, nul, ou perd de 2 buts max.`,
  };
  return map[bet] ?? null;
}

// Probability Bar Component
function ProbabilityBar({ prob, color }: { prob: number; color: string }) {
  return (
    <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
      <div
        className={`h-full ${color}`}
        style={{ width: `${prob * 100}%` }}
      />
    </div>
  );
}

// Accordion with Dark Theme
function Accordion({ title, icon, children, defaultOpen = false }: AccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-white/5 last:border-b-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-5 hover:bg-white/3 transition group"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <span className="font-semibold text-gray-300 group-hover:text-violet-300 transition">{title}</span>
        </div>
        <span className="text-gray-600 group-hover:text-violet-400 transition">
          {isOpen ? '▼' : '▶'}
        </span>
      </button>
      {isOpen && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}

function getResultIcon(result: 'win' | 'draw' | 'loss') {
  switch (result) {
    case 'win': return '🟢';
    case 'draw': return '🟡';
    case 'loss': return '🔴';
  }
}

function FormDots({ matches, align = 'right' }: { matches: TeamRecentMatch[]; align?: 'left' | 'right' }) {
  return (
    <div className={`flex items-center gap-1.5 mt-1.5 ${align === 'right' ? 'justify-end' : 'justify-start'}`}>
      {matches.slice(0, 5).map((m, i) => (
        <div
          key={i}
          title={`${m.date} vs ${m.opponent}: ${m.score}`}
          className={`w-2.5 h-2.5 rounded-full ring-1 ring-black/30 ${
            m.result === 'win' ? 'bg-emerald-400' :
            m.result === 'draw' ? 'bg-yellow-400' :
            'bg-red-500'
          }`}
        />
      ))}
    </div>
  );
}


export default function MatchCard({ prediction }: { prediction: MatchPrediction }) {
  const hasEdge = prediction.edge && prediction.best_odds;

  // Find max edge
  const maxEdge = hasEdge ? Math.max(
    prediction.edge!.home,
    prediction.edge!.draw,
    prediction.edge!.away
  ) : 0;

  return (
    <div className={`bg-white/3 rounded-xl border overflow-hidden ${maxEdge > 10 ? 'border-violet-500/40' : 'border-white/8'} hover:border-violet-500/20 transition`}>

      {/* Header */}
      <div className="relative border-b border-white/5 p-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="text-xs font-mono uppercase tracking-widest text-gray-500">
              {prediction.league}
            </div>
            {prediction.is_european && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold font-mono border ${
                prediction.league_slug === 'champions_league'
                  ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                  : prediction.league_slug === 'europa_league'
                  ? 'bg-orange-500/20 border-orange-500/50 text-orange-400'
                  : 'bg-green-500/20 border-green-500/50 text-green-400'
              }`}>
                {prediction.league_slug === 'champions_league' ? 'UCL' :
                 prediction.league_slug === 'europa_league' ? 'UEL' : 'UECL'}
              </span>
            )}
          </div>
          <div className="text-xs font-mono text-violet-400">
            {new Date(prediction.kickoff).toLocaleDateString('fr-FR', {
              weekday: 'short',
              day: 'numeric',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit'
            })}
          </div>
        </div>

        <div className="flex items-center justify-between gap-6">
          {/* Home Team */}
          <div className="flex-1 text-right">
            <div className="text-lg sm:text-2xl font-bold text-white mb-1 truncate">{prediction.home_team}</div>
            {prediction.home_stats && prediction.home_stats.recent_matches.length > 0 && (
              <FormDots matches={prediction.home_stats.recent_matches} align="right" />
            )}
          </div>

          {/* VS Divider */}
          <div className="flex flex-col items-center gap-2">
            <div className="text-3xl font-bold text-transparent bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text">
              VS
            </div>
            {/* Show confidence badge if available, otherwise show edge badge */}
            {prediction.confidence_badge ? (
              getConfidenceBadge(prediction.confidence_badge)
            ) : (
              maxEdge > 10 && getEdgeBadge(maxEdge)
            )}
          </div>

          {/* Away Team */}
          <div className="flex-1 text-left">
            <div className="text-lg sm:text-2xl font-bold text-white mb-1 truncate">{prediction.away_team}</div>
            {prediction.away_stats && prediction.away_stats.recent_matches.length > 0 && (
              <FormDots matches={prediction.away_stats.recent_matches} align="left" />
            )}
          </div>
        </div>
      </div>

      {/* PREDICTION + PARIS SUGGÉRÉ — always visible */}
      <div className="grid grid-cols-1 sm:grid-cols-2 sm:divide-x divide-white/5 border-b border-white/5">

        {/* LEFT: Prédiction du modèle */}
        <div className="p-5">
          <div className="text-xs font-mono uppercase tracking-wider text-gray-500 mb-4">
            Prédiction du modèle
          </div>
          <div className="space-y-3">
            {(['home', 'draw', 'away'] as const).map((outcome) => {
              const prob = prediction.model_probs[outcome];
              const label = outcome === 'home' ? prediction.home_team
                          : outcome === 'away' ? prediction.away_team
                          : 'Nul';
              const isTop = prob === Math.max(prediction.model_probs.home, prediction.model_probs.draw, prediction.model_probs.away);
              return (
                <div key={outcome}>
                  <div className="flex justify-between items-center mb-1">
                    <span className={`text-sm font-medium truncate max-w-[120px] ${isTop ? 'text-white' : 'text-gray-500'}`}>
                      {label}
                    </span>
                    <span className={`text-sm font-bold font-mono ml-2 ${isTop ? 'text-violet-400' : 'text-gray-600'}`}>
                      {(prob * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isTop ? 'bg-gradient-to-r from-violet-500 to-fuchsia-500' : 'bg-white/10'}`}
                      style={{ width: `${prob * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT: Paris recommandé */}
        {(() => {
          const bet = prediction.recommended_bet;
          if (!bet) {
            return (
              <div className="p-5 flex flex-col items-center justify-center gap-3">
                <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-xl">
                  🚫
                </div>
                <div className="text-center">
                  <div className="text-sm font-semibold text-gray-400">Aucun pari recommandé</div>
                  <div className="text-xs text-gray-600 mt-1 font-mono">Edge insuffisant sur ce match</div>
                </div>
              </div>
            );
          }
          const betLabel = bet === 'home' ? `1 — ${prediction.home_team}`
            : bet === 'away' ? `2 — ${prediction.away_team}`
            : bet === 'draw' ? 'Match nul'
            : bet === 'over25' ? 'Total buts +2,5'
            : bet === 'under25' ? 'Total buts -2,5'
            : bet === 'over15' ? 'Total buts +1,5'
            : bet === 'under15' ? 'Total buts -1,5'
            : bet === 'over35' ? 'Total buts +3,5'
            : bet === 'under35' ? 'Total buts -3,5'
            : bet === 'btts_yes' ? 'Les deux équipes marquent — Oui'
            : bet === 'btts_no' ? 'Les deux équipes marquent — Non'
            : bet === 'dc_1x' ? `Double chance 1X (${prediction.home_team}/Nul)`
            : bet === 'dc_x2' ? `Double chance X2 (Nul/${prediction.away_team})`
            : bet === 'dc_12' ? `Double chance 12 (${prediction.home_team}/${prediction.away_team})`
            : bet === 'dnb_home' ? `Nul remboursé — ${prediction.home_team}`
            : bet === 'dnb_away' ? `Nul remboursé — ${prediction.away_team}`
            : bet === 'spread_home_m15' ? `Handicap — ${prediction.home_team} (-1,5)`
            : bet === 'spread_away_p15' ? `Handicap — ${prediction.away_team} (+1,5)`
            : bet === 'spread_home_m25' ? `Handicap — ${prediction.home_team} (-2,5)`
            : bet === 'spread_away_p25' ? `Handicap — ${prediction.away_team} (+2,5)`
            : bet;
          const odds = getBetOdds(prediction);
          const edge = getBetEdge(prediction);
          const prob = getBetProb(prediction);
          return (
            <div className="flex flex-col">
              {/* Header banner */}
              <div className="px-5 py-2.5 bg-gradient-to-r from-violet-600/25 to-fuchsia-600/15 border-b border-violet-500/30 flex items-center gap-2">
                <span className="text-violet-400 text-base leading-none">✦</span>
                <span className="text-xs font-black uppercase tracking-widest text-violet-300 font-mono">Pari conseillé</span>
              </div>

              {/* Body */}
              <div className="flex-1 p-5 flex flex-col justify-between gap-4 bg-gradient-to-b from-violet-500/5 to-transparent">

                {/* Bet name — big and bold */}
                <div>
                  <div className="text-base font-black text-white leading-snug mb-1">{betLabel}</div>
                  {(() => {
                    const expl = getBetExplanation(bet, prediction.home_team, prediction.away_team);
                    return expl ? (
                      <div className="text-xs text-gray-500 leading-relaxed">{expl}</div>
                    ) : null;
                  })()}
                </div>

                {/* Chips row */}
                <div className="grid grid-cols-3 gap-2">
                  {odds !== null ? (
                    <div className="flex flex-col items-center gap-0.5 px-2 py-2 rounded-lg bg-yellow-400/10 border border-yellow-400/30">
                      <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Cote</span>
                      <span className="text-base font-black text-yellow-400 font-mono leading-none">{odds.toFixed(2)}</span>
                    </div>
                  ) : <div />}
                  {prob !== null ? (
                    <div className="flex flex-col items-center gap-0.5 px-2 py-2 rounded-lg bg-violet-500/10 border border-violet-500/30">
                      <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Prob.</span>
                      <span className="text-base font-black text-violet-300 font-mono leading-none">{(prob * 100).toFixed(0)}%</span>
                    </div>
                  ) : <div />}
                  {edge !== null ? (
                    <div className="flex flex-col items-center gap-0.5 px-2 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                      <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Edge</span>
                      <span className="text-base font-black text-emerald-400 font-mono leading-none">+{edge.toFixed(1)}%</span>
                    </div>
                  ) : <div />}
                </div>

                {/* Kelly */}
                {prediction.kelly_stake && prediction.kelly_stake > 0 && (
                  <div className="text-xs text-gray-500 font-mono text-center border-t border-violet-500/20 pt-3">
                    Mise Kelly : <span className="text-violet-300 font-bold">{prediction.kelly_stake.toFixed(1)}%</span> de ta bankroll
                  </div>
                )}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Accordions */}
      <div className="relative">
        {/* 1. Model Predictions */}
        <Accordion title="Prédictions & Cotes" icon="📈" defaultOpen={false}>
          <div className="space-y-6">
            {/* 1X2 Probabilities */}
            <div className="grid grid-cols-3 gap-4">
              {['home', 'draw', 'away'].map((outcome) => {
                const prob = prediction.model_probs[outcome as keyof typeof prediction.model_probs];
                const edge = hasEdge ? prediction.edge![outcome as keyof typeof prediction.edge] : 0;
                const odds = hasEdge ? prediction.best_odds![outcome as keyof typeof prediction.best_odds] : 0;
                return (
                  <div
                    key={outcome}
                    className={`relative p-4 rounded-lg border-2 ${
                      edge > 5
                        ? getEdgeBgClass(edge) + ' shadow-lg'
                        : 'bg-white/3 border-white/5'
                    }`}
                  >
                    {/* Edge Badge */}
                    {edge > 8 && (
                      <div className="absolute -top-2 -right-2">
                        {getEdgeBadge(edge)}
                      </div>
                    )}

                    {/* Label */}
                    <div className="text-xs text-gray-500 uppercase font-mono mb-2">
                      {outcome === 'home' ? prediction.home_team.substring(0, 10) :
                       outcome === 'draw' ? 'Nul' : prediction.away_team.substring(0, 10)}
                    </div>

                    {/* Probability */}
                    <div className={`text-3xl font-bold mb-2 ${
                      edge > 5 ? getEdgeColorClass(edge) : 'text-gray-300'
                    }`}>
                      {(prob * 100).toFixed(1)}%
                    </div>

                    {/* Progress Bar */}
                    <ProbabilityBar
                      prob={prob}
                      color={edge > 5 ? 'bg-gradient-to-r from-violet-500 to-fuchsia-500' : 'bg-white/10'}
                    />

                    {/* Odds & Edge */}
                    {hasEdge && (
                      <div className="mt-3 space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500 font-mono">Cote:</span>
                          <span className="text-gray-300 font-bold font-mono">{odds.toFixed(2)}</span>
                        </div>
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500 font-mono">Edge:</span>
                          <span className={`font-bold font-mono ${
                            edge > 5 ? getEdgeColorClass(edge) : 'text-gray-600'
                          }`}>
                            {edge > 0 ? '+' : ''}{edge.toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Over/Under 2.5 */}
            {prediction.over_under && (
              <div className="mt-6 p-4 bg-white/3 rounded-lg border border-white/8">
                <div className="text-sm font-semibold text-gray-400 mb-4 flex items-center gap-2">
                  <span>⚽</span> Over/Under 2.5 Buts
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {['over_25', 'under_25'].map((market) => {
                    const prob = prediction.over_under![market as keyof typeof prediction.over_under];
                    const edge = prediction.over_under_edge
                      ? prediction.over_under_edge[market as keyof typeof prediction.over_under_edge]
                      : 0;
                    const odds = prediction.over_under_odds
                      ? prediction.over_under_odds[market as keyof typeof prediction.over_under_odds]
                      : 0;

                    return (
                      <div
                        key={market}
                        className={`p-3 rounded-lg border ${
                          edge > 5
                            ? getEdgeBgClass(edge)
                            : 'bg-white/3 border-white/5'
                        }`}
                      >
                        <div className="text-xs text-gray-500 uppercase font-mono mb-1">
                          {market === 'over_25' ? '+2,5 buts' : '-2,5 buts'}
                        </div>
                        <div className={`text-2xl font-bold ${
                          edge > 5 ? getEdgeColorClass(edge) : 'text-gray-300'
                        }`}>
                          {(prob * 100).toFixed(1)}%
                        </div>
                        <ProbabilityBar
                          prob={prob}
                          color={edge > 5 ? 'bg-gradient-to-r from-violet-500 to-fuchsia-500' : 'bg-white/10'}
                        />
                        {odds > 0 && (
                          <div className="mt-2 flex items-center justify-between text-xs">
                            <span className="text-gray-500 font-mono">Cote: {odds.toFixed(2)}</span>
                            <span className={`font-bold font-mono ${
                              edge > 3 ? getEdgeColorClass(edge) : 'text-gray-600'
                            }`}>
                              {edge > 0 ? '+' : ''}{edge.toFixed(1)}%
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </Accordion>

        {/* 2. Recent Stats */}
        {(prediction.home_stats || prediction.away_stats) && (
          <Accordion title="Stats Récentes (L5)" icon="📊">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
              {/* Home Stats */}
              {prediction.home_stats && (
                <div className="p-4 bg-white/3 rounded-lg border border-white/8">
                  <div className="text-sm font-semibold text-violet-400 mb-4 flex items-center gap-2">
                    🏠 {prediction.home_team}
                  </div>
                  <div className="space-y-3">
                    <StatRow label="PPG" value={prediction.home_stats.ppg.toFixed(1)} />
                    <StatRow label="Buts marqués" value={`${prediction.home_stats.goals_scored_avg.toFixed(1)}/m`} />
                    <StatRow label="Buts encaissés" value={`${prediction.home_stats.goals_conceded_avg.toFixed(1)}/m`} />
                    <StatRow label="Tirs cadrés" value={`${prediction.home_stats.shots_on_target_per_game.toFixed(1)}/m`} />
                    <StatRow label="Précision" value={`${prediction.home_stats.shot_accuracy.toFixed(0)}%`} />
                    <div className="pt-2 border-t border-white/5">
                      <StatRow
                        label="Dominance"
                        value={`${(prediction.home_stats.dominance_score * 100).toFixed(0)}%`}
                        highlight={prediction.home_stats.dominance_score > 0.55}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Away Stats */}
              {prediction.away_stats && (
                <div className="p-4 bg-white/3 rounded-lg border border-white/8">
                  <div className="text-sm font-semibold text-orange-400 mb-4 flex items-center gap-2">
                    ✈️ {prediction.away_team}
                  </div>
                  <div className="space-y-3">
                    <StatRow label="PPG" value={prediction.away_stats.ppg.toFixed(1)} />
                    <StatRow label="Buts marqués" value={`${prediction.away_stats.goals_scored_avg.toFixed(1)}/m`} />
                    <StatRow label="Buts encaissés" value={`${prediction.away_stats.goals_conceded_avg.toFixed(1)}/m`} />
                    <StatRow label="Tirs cadrés" value={`${prediction.away_stats.shots_on_target_per_game.toFixed(1)}/m`} />
                    <StatRow label="Précision" value={`${prediction.away_stats.shot_accuracy.toFixed(0)}%`} />
                    <div className="pt-2 border-t border-white/5">
                      <StatRow
                        label="Dominance"
                        value={`${(prediction.away_stats.dominance_score * 100).toFixed(0)}%`}
                        highlight={prediction.away_stats.dominance_score > 0.55}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Accordion>
        )}

        {/* 3. Last 5 Matches Detail */}
        {(prediction.home_stats?.recent_matches || prediction.away_stats?.recent_matches) && (
          <Accordion title="Derniers Matchs (L5)" icon="⚽">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
              {/* Home recent matches */}
              {prediction.home_stats?.recent_matches && (
                <div>
                  <div className="text-sm font-semibold text-violet-400 mb-3 flex items-center gap-2">
                    🏠 {prediction.home_team}
                  </div>
                  <div className="space-y-2">
                    {prediction.home_stats.recent_matches.map((match, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 p-3 bg-white/3 rounded-lg border border-white/5 hover:border-violet-500/30 transition"
                      >
                        <span className="text-xl">{getResultIcon(match.result)}</span>
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-gray-200 text-sm">
                            {match.score} <span className="text-gray-500">vs</span> {match.opponent}
                          </div>
                          <div className="text-xs text-gray-500 font-mono mt-1">
                            {match.date} • {match.home_away === 'home' ? '🏠' : '✈️'}
                            {match.clean_sheet && <span className="ml-2 text-emerald-400">🛡️ CS</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Away recent matches */}
              {prediction.away_stats?.recent_matches && (
                <div>
                  <div className="text-sm font-semibold text-orange-400 mb-3 flex items-center gap-2">
                    ✈️ {prediction.away_team}
                  </div>
                  <div className="space-y-2">
                    {prediction.away_stats.recent_matches.map((match, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 p-3 bg-white/3 rounded-lg border border-white/5 hover:border-orange-500/30 transition"
                      >
                        <span className="text-xl">{getResultIcon(match.result)}</span>
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-gray-200 text-sm">
                            {match.score} <span className="text-gray-500">vs</span> {match.opponent}
                          </div>
                          <div className="text-xs text-gray-500 font-mono mt-1">
                            {match.date} • {match.home_away === 'home' ? '🏠' : '✈️'}
                            {match.clean_sheet && <span className="ml-2 text-emerald-400">🛡️ CS</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Accordion>
        )}

        {/* 4. Head-to-Head */}
        {prediction.h2h_stats && (
          <Accordion title="Face-à-Face (H2H)" icon="🤝">
            <div className="space-y-4">
              {/* Win Distribution */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-4 bg-violet-500/10 rounded-lg border border-violet-500/30 text-center">
                  <div className="text-3xl font-bold text-violet-400">{prediction.h2h_stats.home_wins}</div>
                  <div className="text-xs text-gray-400 mt-1 font-mono uppercase">
                    {prediction.home_team.substring(0, 10)}
                  </div>
                </div>
                <div className="p-4 bg-white/3 rounded-lg border border-white/8 text-center">
                  <div className="text-3xl font-bold text-gray-400">{prediction.h2h_stats.draws}</div>
                  <div className="text-xs text-gray-600 mt-1 font-mono uppercase">Nuls</div>
                </div>
                <div className="p-4 bg-orange-500/10 rounded-lg border border-orange-500/30 text-center">
                  <div className="text-3xl font-bold text-orange-400">{prediction.h2h_stats.away_wins}</div>
                  <div className="text-xs text-gray-400 mt-1 font-mono uppercase">
                    {prediction.away_team.substring(0, 10)}
                  </div>
                </div>
              </div>

              {/* Stats Summary */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-white/3 rounded-lg border border-white/5">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-500 text-xs font-mono uppercase">Moy. Buts</span>
                    <span className="text-gray-200 font-bold font-mono">{prediction.h2h_stats.avg_goals.toFixed(1)}</span>
                  </div>
                </div>
                <div className="p-3 bg-white/3 rounded-lg border border-white/5">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-500 text-xs font-mono uppercase">+2,5 buts</span>
                    <span className="text-gray-200 font-bold font-mono">{prediction.h2h_stats.over_25_rate.toFixed(0)}%</span>
                  </div>
                </div>
              </div>

              {/* Recent Results */}
              {prediction.h2h_stats.recent_results && (
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-3 uppercase font-mono">
                    Derniers résultats
                  </div>
                  <div className="space-y-2">
                    {prediction.h2h_stats.recent_results.map((result, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 bg-white/3 rounded-lg border border-white/5"
                      >
                        <span className="text-gray-500 text-sm font-mono">{result.date}</span>
                        <span className="text-gray-200 font-bold font-mono">{result.score}</span>
                        <span className="text-xl">
                          {result.result === 'home_win' ? '🟢' :
                           result.result === 'draw' ? '🟡' : '🔴'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Accordion>
        )}

        {/* 5. Top Scores */}
        {prediction.correct_score && (
          <Accordion title="Scores Exacts (Top 5)" icon="🎯">
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
              {Object.entries(prediction.correct_score).slice(0, 5).map(([score, prob], idx) => (
                <div
                  key={score}
                  className="relative p-4 bg-white/3 rounded-lg border border-white/8 hover:border-violet-500/40 transition text-center group"
                >
                  <div className="text-xs text-gray-500 font-mono mb-1">#{idx + 1}</div>
                  <div className="text-3xl font-bold text-violet-400 group-hover:text-fuchsia-400 transition">
                    {score}
                  </div>
                  <div className="text-xs text-gray-400 mt-2 font-mono">
                    {(prob * 100).toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>
          </Accordion>
        )}

        {/* 6. Educational Guide */}
        <Accordion title="Guide & Avertissements" icon="📚">
          <div className="space-y-4">
            <div className="p-4 bg-violet-500/10 border-l-4 border-violet-500 rounded-r-lg">
              <h4 className="text-sm font-bold text-violet-400 mb-2 font-mono uppercase">
                💡 Comment utiliser ces données ?
              </h4>
              <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
                <li>Compare les stats récentes (forme, buts, tirs)</li>
                <li>Analyse les confrontations directes (H2H)</li>
                <li>Repère les edges positifs (écarts avec le marché)</li>
                <li>Focus sur les badges 🔥 HOT et ⚡ VALUE</li>
                <li className="text-emerald-400 font-semibold">Règle: Max 1-2% de ta bankroll par pari</li>
              </ul>
            </div>

            <div className="p-4 bg-orange-500/10 border-l-4 border-orange-500 rounded-r-lg">
              <h4 className="text-sm font-bold text-orange-400 mb-2 font-mono uppercase">
                ⚠️ Avertissement Légal
              </h4>
              <p className="text-sm text-gray-400 leading-relaxed">
                Ces prédictions sont purement statistiques et ne garantissent aucun résultat.
                Les paris comportent des risques financiers. Parie uniquement ce que tu peux te permettre de perdre.
                Si tu as un problème avec les jeux d'argent, contacte <strong className="text-orange-400">Joueurs Info Service</strong> au 09 74 75 13 13.
              </p>
            </div>
          </div>
        </Accordion>
      </div>
    </div>
  );
}

// Stat Row Component
function StatRow({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500 font-mono text-xs uppercase">{label}</span>
      <span className={`font-bold font-mono ${
        highlight ? 'text-emerald-400' : 'text-gray-200'
      }`}>
        {value}
      </span>
    </div>
  );
}
