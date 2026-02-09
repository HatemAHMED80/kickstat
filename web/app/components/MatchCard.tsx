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

interface MatchPrediction {
  match_id: string;
  league: string;
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
}

interface AccordionProps {
  title: string;
  icon: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

// Utility: Get edge color and style
function getEdgeColorClass(edge: number): string {
  if (edge > 15) return 'text-emerald-400';
  if (edge > 8) return 'text-cyan-400';
  if (edge > 3) return 'text-blue-400';
  return 'text-gray-500';
}

function getEdgeBgClass(edge: number): string {
  if (edge > 15) return 'bg-emerald-500/10 border-emerald-500/50 shadow-emerald-500/20';
  if (edge > 8) return 'bg-cyan-500/10 border-cyan-500/50 shadow-cyan-500/20';
  if (edge > 3) return 'bg-blue-500/10 border-blue-500/50 shadow-blue-500/20';
  return 'bg-gray-800/30 border-gray-700/30';
}

function getEdgeBadge(edge: number): React.ReactNode {
  if (edge > 15) {
    return (
      <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold animate-pulse">
        🔥 HOT
      </div>
    );
  }
  if (edge > 8) {
    return (
      <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-cyan-500/20 border border-cyan-500/50 text-cyan-400 text-xs font-bold">
        ⚡ VALUE
      </div>
    );
  }
  return null;
}

// Confidence Badge Component
function getConfidenceBadge(badge: string | null | undefined): React.ReactNode {
  if (!badge) return null;

  if (badge === "SAFE") {
    return (
      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-500/20 border border-blue-500/50 text-blue-400 text-xs font-bold">
        🛡️ SAFE BET
      </div>
    );
  }
  if (badge === "VALUE") {
    return (
      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-cyan-500/20 border border-cyan-500/50 text-cyan-400 text-xs font-bold">
        💎 VALUE
      </div>
    );
  }
  if (badge === "RISKY") {
    return (
      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/20 border border-orange-500/50 text-orange-400 text-xs font-bold">
        ⚠️ RISKY
      </div>
    );
  }
  return null;
}

// Probability Bar Component
function ProbabilityBar({ prob, color }: { prob: number; color: string }) {
  return (
    <div className="w-full h-2 bg-gray-800/50 rounded-full overflow-hidden">
      <div
        className={`h-full ${color} transition-all duration-700 ease-out`}
        style={{ width: `${prob * 100}%` }}
      />
    </div>
  );
}

// Accordion with Dark Theme
function Accordion({ title, icon, children, defaultOpen = false }: AccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-gray-800/50 last:border-b-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-5 hover:bg-gray-800/20 transition group"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <span className="font-semibold text-gray-200 group-hover:text-cyan-400 transition">{title}</span>
        </div>
        <span className="text-gray-600 group-hover:text-cyan-400 transition">
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

function getFormString(matches: TeamRecentMatch[]): string {
  return matches.map(m => getResultIcon(m.result)).join('');
}

export default function MatchCard({ prediction }: { prediction: MatchPrediction }) {
  const maxProb = Math.max(
    prediction.model_probs.home,
    prediction.model_probs.draw,
    prediction.model_probs.away
  );

  const bestOutcome =
    prediction.model_probs.home === maxProb ? 'home' :
    prediction.model_probs.draw === maxProb ? 'draw' : 'away';

  const hasEdge = prediction.edge && prediction.best_odds;

  // Find max edge
  const maxEdge = hasEdge ? Math.max(
    prediction.edge!.home,
    prediction.edge!.draw,
    prediction.edge!.away
  ) : 0;

  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-900 to-black rounded-xl shadow-2xl border border-gray-800 overflow-hidden relative">
      {/* Glow effect for high-value bets */}
      {maxEdge > 10 && (
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-emerald-500/10 to-cyan-500/10 blur-xl opacity-50" />
      )}

      {/* Header */}
      <div className="relative bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 border-b border-cyan-500/20 p-6">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-mono uppercase tracking-widest text-gray-500">
            {prediction.league}
          </div>
          <div className="text-xs font-mono text-cyan-400">
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
            <div className="text-2xl font-bold text-white mb-1">{prediction.home_team}</div>
            {prediction.home_stats && (
              <div className="text-sm opacity-80 text-gray-400">
                {getFormString(prediction.home_stats.recent_matches.slice(0, 5))}
              </div>
            )}
          </div>

          {/* VS Divider */}
          <div className="flex flex-col items-center gap-2">
            <div className="text-3xl font-bold text-transparent bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text">
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
            <div className="text-2xl font-bold text-white mb-1">{prediction.away_team}</div>
            {prediction.away_stats && (
              <div className="text-sm opacity-80 text-gray-400">
                {getFormString(prediction.away_stats.recent_matches.slice(0, 5))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Accordions */}
      <div className="relative">
        {/* 1. Model Predictions */}
        <Accordion title="Prédictions & Cotes" icon="📈" defaultOpen={true}>
          <div className="space-y-6">
            {/* 1X2 Probabilities */}
            <div className="grid grid-cols-3 gap-4">
              {['home', 'draw', 'away'].map((outcome) => {
                const prob = prediction.model_probs[outcome as keyof typeof prediction.model_probs];
                const edge = hasEdge ? prediction.edge![outcome as keyof typeof prediction.edge] : 0;
                const odds = hasEdge ? prediction.best_odds![outcome as keyof typeof prediction.best_odds] : 0;
                const isRecommended = outcome === bestOutcome;

                return (
                  <div
                    key={outcome}
                    className={`relative p-4 rounded-lg border-2 transition-all hover:scale-105 ${
                      edge > 5
                        ? getEdgeBgClass(edge) + ' shadow-lg'
                        : 'bg-gray-800/30 border-gray-700/30'
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
                      color={edge > 5 ? 'bg-gradient-to-r from-cyan-500 to-emerald-500' : 'bg-gray-700'}
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
              <div className="mt-6 p-4 bg-gray-800/20 rounded-lg border border-gray-700/30">
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
                            : 'bg-gray-800/30 border-gray-700/30'
                        }`}
                      >
                        <div className="text-xs text-gray-500 uppercase font-mono mb-1">
                          {market === 'over_25' ? 'OVER 2.5' : 'UNDER 2.5'}
                        </div>
                        <div className={`text-2xl font-bold ${
                          edge > 5 ? getEdgeColorClass(edge) : 'text-gray-300'
                        }`}>
                          {(prob * 100).toFixed(1)}%
                        </div>
                        <ProbabilityBar
                          prob={prob}
                          color={edge > 5 ? 'bg-gradient-to-r from-cyan-500 to-emerald-500' : 'bg-gray-700'}
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
            <div className="grid grid-cols-2 gap-6">
              {/* Home Stats */}
              {prediction.home_stats && (
                <div className="p-4 bg-gray-800/20 rounded-lg border border-gray-700/30">
                  <div className="text-sm font-semibold text-cyan-400 mb-4 flex items-center gap-2">
                    🏠 {prediction.home_team}
                  </div>
                  <div className="space-y-3">
                    <StatRow label="PPG" value={prediction.home_stats.ppg.toFixed(1)} />
                    <StatRow label="Buts marqués" value={`${prediction.home_stats.goals_scored_avg.toFixed(1)}/m`} />
                    <StatRow label="Buts encaissés" value={`${prediction.home_stats.goals_conceded_avg.toFixed(1)}/m`} />
                    <StatRow label="Tirs cadrés" value={`${prediction.home_stats.shots_on_target_per_game.toFixed(1)}/m`} />
                    <StatRow label="Précision" value={`${prediction.home_stats.shot_accuracy.toFixed(0)}%`} />
                    <div className="pt-2 border-t border-gray-700/50">
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
                <div className="p-4 bg-gray-800/20 rounded-lg border border-gray-700/30">
                  <div className="text-sm font-semibold text-orange-400 mb-4 flex items-center gap-2">
                    ✈️ {prediction.away_team}
                  </div>
                  <div className="space-y-3">
                    <StatRow label="PPG" value={prediction.away_stats.ppg.toFixed(1)} />
                    <StatRow label="Buts marqués" value={`${prediction.away_stats.goals_scored_avg.toFixed(1)}/m`} />
                    <StatRow label="Buts encaissés" value={`${prediction.away_stats.goals_conceded_avg.toFixed(1)}/m`} />
                    <StatRow label="Tirs cadrés" value={`${prediction.away_stats.shots_on_target_per_game.toFixed(1)}/m`} />
                    <StatRow label="Précision" value={`${prediction.away_stats.shot_accuracy.toFixed(0)}%`} />
                    <div className="pt-2 border-t border-gray-700/50">
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
            <div className="grid grid-cols-2 gap-6">
              {/* Home recent matches */}
              {prediction.home_stats?.recent_matches && (
                <div>
                  <div className="text-sm font-semibold text-cyan-400 mb-3 flex items-center gap-2">
                    🏠 {prediction.home_team}
                  </div>
                  <div className="space-y-2">
                    {prediction.home_stats.recent_matches.map((match, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 p-3 bg-gray-800/30 rounded-lg border border-gray-700/30 hover:border-cyan-500/30 transition"
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
                        className="flex items-center gap-3 p-3 bg-gray-800/30 rounded-lg border border-gray-700/30 hover:border-orange-500/30 transition"
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
                <div className="p-4 bg-cyan-500/10 rounded-lg border border-cyan-500/30 text-center">
                  <div className="text-3xl font-bold text-cyan-400">{prediction.h2h_stats.home_wins}</div>
                  <div className="text-xs text-gray-400 mt-1 font-mono uppercase">
                    {prediction.home_team.substring(0, 10)}
                  </div>
                </div>
                <div className="p-4 bg-gray-700/30 rounded-lg border border-gray-600/30 text-center">
                  <div className="text-3xl font-bold text-gray-400">{prediction.h2h_stats.draws}</div>
                  <div className="text-xs text-gray-500 mt-1 font-mono uppercase">Nuls</div>
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
                <div className="p-3 bg-gray-800/30 rounded-lg border border-gray-700/30">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-500 text-xs font-mono uppercase">Moy. Buts</span>
                    <span className="text-gray-200 font-bold font-mono">{prediction.h2h_stats.avg_goals.toFixed(1)}</span>
                  </div>
                </div>
                <div className="p-3 bg-gray-800/30 rounded-lg border border-gray-700/30">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-500 text-xs font-mono uppercase">Over 2.5</span>
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
                        className="flex items-center justify-between p-3 bg-gray-800/30 rounded-lg border border-gray-700/30"
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
            <div className="grid grid-cols-5 gap-3">
              {Object.entries(prediction.correct_score).slice(0, 5).map(([score, prob], idx) => (
                <div
                  key={score}
                  className="relative p-4 bg-gradient-to-br from-gray-800/50 to-gray-900/50 rounded-lg border border-gray-700/50 hover:border-cyan-500/50 transition text-center group"
                >
                  <div className="text-xs text-gray-500 font-mono mb-1">#{idx + 1}</div>
                  <div className="text-3xl font-bold text-cyan-400 group-hover:text-emerald-400 transition">
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
            <div className="p-4 bg-cyan-500/10 border-l-4 border-cyan-500 rounded-r-lg">
              <h4 className="text-sm font-bold text-cyan-400 mb-2 font-mono uppercase">
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
