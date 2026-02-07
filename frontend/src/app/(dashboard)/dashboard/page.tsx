'use client';

import { useState, useEffect } from 'react';
import { getOpportunities, getMatchAnalysis, getCompetitions, OpportunityResponse, MatchAnalysisResponse, CompetitionInfo } from '@/lib/api';

type RiskFilter = 'all' | 'safe' | 'medium' | 'risky';

// Country flag mapping
const COUNTRY_FLAGS: Record<string, string> = {
  'France': '🇫🇷',
  'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  'Spain': '🇪🇸',
  'Germany': '🇩🇪',
  'Italy': '🇮🇹',
};

export default function DashboardPage() {
  const [filter, setFilter] = useState<RiskFilter>('all');
  const [selectedLeague, setSelectedLeague] = useState<string | null>(null);
  const [competitions, setCompetitions] = useState<CompetitionInfo[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [freePreviewCount, setFreePreviewCount] = useState(3);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Analysis modal state
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<MatchAnalysisResponse | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Fetch competitions on mount
  useEffect(() => {
    async function fetchCompetitions() {
      try {
        const data = await getCompetitions();
        setCompetitions(data.competitions);
      } catch (err) {
        console.error('[Dashboard] Failed to fetch competitions:', err);
      }
    }
    fetchCompetitions();
  }, []);

  // Fetch opportunities when filters change
  useEffect(() => {
    async function fetchOpportunities() {
      console.log("[Dashboard] Fetching opportunities...");
      try {
        setLoading(true);
        setError(null);
        const data = await getOpportunities({
          min_edge: 5,
          risk_level: filter === 'all' ? undefined : filter,
          competition: selectedLeague || undefined,
          limit: 30,
        });
        console.log("[Dashboard] Got data:", data);
        setOpportunities(data.opportunities);
        setTotal(data.total);
        setFreePreviewCount(data.free_preview_count);
      } catch (err) {
        console.error('[Dashboard] Failed to fetch opportunities:', err);
        setError('Impossible de charger les opportunités');
      } finally {
        setLoading(false);
      }
    }

    fetchOpportunities();
  }, [filter, selectedLeague]);

  // Open analysis modal
  const openAnalysis = async (matchId: number) => {
    setSelectedMatchId(matchId);
    setAnalysisLoading(true);
    try {
      const data = await getMatchAnalysis(matchId);
      setAnalysis(data);
    } catch (err) {
      console.error('Failed to load analysis:', err);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const closeAnalysis = () => {
    setSelectedMatchId(null);
    setAnalysis(null);
  };

  const counts = {
    all: total,
    safe: opportunities.filter(o => o.risk_level === 'safe').length,
    medium: opportunities.filter(o => o.risk_level === 'medium').length,
    risky: opportunities.filter(o => o.risk_level === 'risky').length,
  };

  const lockedCount = total - opportunities.length;

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[12px] font-semibold text-text-2 tracking-wider uppercase flex items-center gap-[7px]">
          <span className="w-[3px] h-3 bg-green rounded" />
          Meilleures opportunités
        </h2>
        <div className="flex gap-[3px] flex-wrap">
          <LeagueButton
            active={selectedLeague === null}
            onClick={() => setSelectedLeague(null)}
            count={total}
          >
            Tous
          </LeagueButton>
          {competitions.map((comp) => (
            <LeagueButton
              key={comp.id}
              active={selectedLeague === comp.name}
              onClick={() => setSelectedLeague(comp.name)}
              flag={COUNTRY_FLAGS[comp.country]}
              count={comp.match_count}
            >
              {comp.short_name}
            </LeagueButton>
          ))}
        </div>
      </div>

      {/* Risk filters */}
      <div className="flex gap-1 mb-3.5 flex-wrap">
        <FilterButton
          active={filter === 'all'}
          onClick={() => setFilter('all')}
          color="white"
          count={counts.all}
        >
          Tout
        </FilterButton>
        <FilterButton
          active={filter === 'safe'}
          onClick={() => setFilter('safe')}
          color="green"
          count={counts.safe}
        >
          Sûr
        </FilterButton>
        <FilterButton
          active={filter === 'medium'}
          onClick={() => setFilter('medium')}
          color="amber"
          count={counts.medium}
        >
          Moyen
        </FilterButton>
        <FilterButton
          active={filter === 'risky'}
          onClick={() => setFilter('risky')}
          color="red"
          count={counts.risky}
        >
          Risqué
        </FilterButton>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex flex-col gap-1.5 mb-7">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-bg-3 border border-border rounded-[10px] h-32 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="bg-red-dark border border-red rounded-[10px] p-4 mb-7 text-center">
          <span className="text-red font-mono text-sm">{error}</span>
          <button
            onClick={() => window.location.reload()}
            className="ml-3 text-text-2 underline text-sm"
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && opportunities.length === 0 && (
        <div className="bg-bg-3 border border-border rounded-[10px] p-8 mb-7 text-center">
          <span className="font-mono text-sm text-text-2">
            Aucune opportunité disponible pour le moment
          </span>
        </div>
      )}

      {/* Opportunities list */}
      {!loading && !error && opportunities.length > 0 && (
        <div className="flex flex-col gap-1.5 mb-7">
          {opportunities.map((opp, idx) => (
            <OpportunityCard
              key={opp.id}
              opportunity={opp}
              index={idx}
              onAnalyze={() => openAnalysis(opp.match.id)}
            />
          ))}
        </div>
      )}

      {/* Locked banner */}
      {lockedCount > 0 && (
        <div className="bg-bg-3 border border-border rounded-[10px] py-3.5 px-[18px] flex items-center justify-center gap-2.5 flex-wrap">
          <span className="font-mono text-[11px] text-text-2">
            🔒 {lockedCount} opportunités supplémentaires
          </span>
          <button className="font-mono text-[10px] px-3.5 py-1.5 rounded bg-green text-bg font-semibold hover:shadow-[0_0_14px_rgba(0,232,123,0.2)] transition-all">
            9,99€/mois → Tout voir
          </button>
          <button className="font-mono text-[10px] px-3.5 py-1.5 rounded bg-transparent text-text-2 font-semibold border border-border hover:border-border-2 hover:text-text-1 transition-all">
            0,99€ par match
          </button>
        </div>
      )}

      {/* History section */}
      <div className="mt-7">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-[12px] font-semibold text-text-2 tracking-wider uppercase flex items-center gap-[7px]">
            <span className="w-[3px] h-3 bg-green rounded" />
            Historique — 30 jours
          </h2>
          <span className="font-mono text-[9px] text-text-3 bg-bg-3 border border-border rounded px-2 py-1">
            247/361 · 68.4%
          </span>
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(36px,1fr))] gap-[3px] mt-2">
          {Array.from({ length: 30 }).map((_, i) => {
            const isWin = Math.random() > 0.316;
            return (
              <div
                key={i}
                className={`aspect-square rounded flex items-center justify-center font-mono text-[8px] font-semibold ${
                  isWin
                    ? 'bg-green-dark text-green border border-[rgba(0,232,123,0.08)]'
                    : 'bg-red-dark text-red border border-[rgba(255,68,102,0.08)]'
                }`}
              >
                {isWin ? '✓' : '✗'}
              </div>
            );
          })}
        </div>
      </div>

      {/* CTA */}
      <div className="mt-9 bg-gradient-to-br from-bg-3 to-[#12121c] border border-border rounded-xl p-[30px] text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(0,232,123,0.08),transparent_60%)] pointer-events-none" />

        <div className="font-mono text-[8px] text-green tracking-[3px] uppercase mb-[7px] relative">
          Premium
        </div>
        <h3 className="text-[22px] font-extrabold text-text-1 tracking-tight mb-1 relative">
          Les maths, pas les émotions.
        </h3>
        <p className="text-[12px] text-text-2 mb-5 relative">
          Toutes les opportunités. Tous les matchs. Chaque journée.
        </p>

        <div className="flex justify-center gap-2.5 flex-wrap relative">
          <PricingCard
            price="0,99€"
            period="par match"
            features={['Toutes les opportunités', 'Marchés + buteurs', 'Combinés détectés']}
          />
          <PricingCard
            price="9,99€"
            period="par mois"
            features={['L1 + L2 complets', 'Combinés à forte cote', 'Alertes en temps réel', 'Historique complet']}
            featured
          />
          <PricingCard
            price="24,99€"
            period="par mois"
            features={['Tout le mensuel', 'Accès API', 'Multi-matchs']}
            label="Pro"
          />
        </div>
      </div>

      {/* Analysis Modal */}
      {selectedMatchId && (
        <MatchAnalysisModal
          analysis={analysis}
          loading={analysisLoading}
          onClose={closeAnalysis}
        />
      )}
    </div>
  );
}

// =============================================================================
// COMPONENTS
// =============================================================================

function LeagueButton({
  children,
  active,
  onClick,
  flag,
  count,
}: {
  children: React.ReactNode;
  active?: boolean;
  onClick?: () => void;
  flag?: string;
  count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`font-mono text-[10px] px-[11px] py-1.5 rounded border transition-all flex items-center gap-1.5 ${
        active
          ? 'bg-green-dark border-green text-green'
          : 'bg-transparent border-border text-text-2 hover:border-border-2 hover:text-text-1'
      }`}
    >
      {flag && <span>{flag}</span>}
      {children}
      {count !== undefined && (
        <span className={`text-[8px] px-1 py-0.5 rounded ${active ? 'bg-green/20' : 'bg-bg-3'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

function FilterButton({
  children,
  active,
  onClick,
  color,
  count,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  color: 'white' | 'green' | 'amber' | 'red';
  count: number;
}) {
  const dotColors = {
    white: 'bg-text-2',
    green: 'bg-green',
    amber: 'bg-amber',
    red: 'bg-red',
  };

  return (
    <button
      onClick={onClick}
      className={`font-mono text-[10px] px-3 py-1.5 rounded-full border flex items-center gap-1.5 transition-all ${
        active
          ? 'border-text-2 text-text-1 bg-[rgba(255,255,255,0.03)]'
          : 'border-border text-text-2 hover:border-border-2'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColors[color]}`} />
      {children}
      <span className="text-[9px] bg-[rgba(255,255,255,0.05)] px-1.5 py-0.5 rounded-lg text-text-3">
        {count}
      </span>
    </button>
  );
}

function OpportunityCard({
  opportunity: opp,
  index,
  onAnalyze,
}: {
  opportunity: OpportunityResponse;
  index: number;
  onAnalyze: () => void;
}) {
  const riskColors = {
    safe: { text: 'text-green', bg: 'bg-green-dark', border: 'border-l-green' },
    medium: { text: 'text-amber', bg: 'bg-amber-dark', border: 'border-l-amber' },
    risky: { text: 'text-red', bg: 'bg-red-dark', border: 'border-l-red' },
  };

  const colors = riskColors[opp.risk_level];
  const confFillColors = {
    safe: 'bg-green',
    medium: 'bg-amber',
    risky: 'bg-red',
  };

  // Format date - kickoff is UTC, display in Paris timezone
  const kickoffDate = new Date(opp.match.kickoff + 'Z'); // Ensure UTC interpretation
  const dateStr = kickoffDate.toLocaleDateString('fr-FR', {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Paris',
  });

  // Match display
  const matchDisplay = `${opp.match.home_team.name} vs ${opp.match.away_team.name}`;

  return (
    <div
      className={`bg-gradient-to-br from-bg-3 to-[#12121c] border border-border rounded-[10px] overflow-hidden transition-all hover:border-border-2 hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)] relative border-l-[3px] ${colors.border}`}
      style={{ animationDelay: `${index * 0.03}s` }}
    >
      <div className="grid grid-cols-[1fr_auto] gap-3 p-3.5 pl-5 items-center">
        {/* Left side */}
        <div className="flex flex-col gap-1.5">
          {/* Top row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`font-mono text-[8px] font-bold tracking-wider uppercase py-0.5 px-[7px] rounded ${colors.text} ${colors.bg}`}>
              {opp.risk_level === 'safe' ? 'SÛR' : opp.risk_level === 'medium' ? 'MOYEN' : 'RISQUÉ'}
            </span>
            {opp.match.competition_name && (
              <span className="font-mono text-[8px] text-text-3 bg-[rgba(255,255,255,0.03)] px-1.5 py-0.5 rounded">
                {opp.match.competition_name}
              </span>
            )}
            <span className="font-mono text-[9px] text-text-3 tracking-wide">
              {matchDisplay} · {dateStr}
            </span>
          </div>

          {/* Bet description */}
          <div className="text-[15px] font-bold text-text-1 tracking-tight leading-snug">
            {opp.market_display}
          </div>

          {/* Confidence bar */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-[8.5px] text-text-3 uppercase tracking-wider min-w-[68px]">
              Notre modèle
            </span>
            <div className="flex-1 max-w-[180px] h-1.5 bg-border rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${confFillColors[opp.risk_level]}`}
                style={{ width: `${opp.model_probability * 100}%` }}
              />
            </div>
            <span className={`font-mono text-[11px] font-semibold min-w-[32px] ${colors.text}`}>
              {(opp.model_probability * 100).toFixed(0)}%
            </span>
          </div>

          {/* Edge row */}
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="font-mono text-[8.5px] text-text-3 uppercase tracking-wider min-w-[68px] flex items-center gap-1">
              Avantage
              <span className="w-3 h-3 rounded-full bg-[rgba(255,255,255,0.04)] border border-border text-[7px] flex items-center justify-center text-text-3 cursor-help">
                i
              </span>
            </span>
            <div className="flex-1 max-w-[180px] h-[3px] bg-border rounded overflow-hidden">
              <div
                className="h-full rounded bg-green opacity-50"
                style={{ width: `${Math.min(opp.edge_percentage * 5, 100)}%` }}
              />
            </div>
            <span className="font-mono text-[10.5px] font-semibold text-green">
              +{opp.edge_percentage.toFixed(1)}%
            </span>
          </div>

          {/* Bookmaker info */}
          <div className="flex items-center gap-2 mt-0.5">
            <span className="font-mono text-[8px] text-text-3">
              via {opp.bookmaker_name}
            </span>
            {opp.kelly_stake && (
              <span className="font-mono text-[8px] text-text-3 bg-[rgba(255,255,255,0.03)] px-1.5 py-0.5 rounded">
                Kelly: {(opp.kelly_stake * 100).toFixed(1)}%
              </span>
            )}
          </div>
        </div>

        {/* Right side - Odds & Analyze */}
        <div className="flex flex-col items-center justify-center gap-2">
          <div className="min-w-[80px] py-2 px-3 bg-[rgba(255,255,255,0.015)] rounded-lg border border-border text-center">
            <span className="font-mono text-[7.5px] text-text-3 uppercase tracking-[1.2px] mb-0.5 block">
              Cote
            </span>
            <span className="font-mono text-[24px] font-bold text-cyan leading-none">
              {opp.best_odds.toFixed(2)}
            </span>
          </div>
          <button
            onClick={onAnalyze}
            className="font-mono text-[9px] px-3 py-1.5 rounded bg-[rgba(0,232,123,0.1)] text-green border border-green/30 hover:bg-[rgba(0,232,123,0.2)] hover:border-green/50 transition-all"
          >
            Analyse complète →
          </button>
        </div>
      </div>
    </div>
  );
}

function PricingCard({
  price,
  period,
  features,
  featured,
  label,
}: {
  price: string;
  period: string;
  features: string[];
  featured?: boolean;
  label?: string;
}) {
  return (
    <div
      className={`bg-bg border rounded-[10px] p-4 px-5 text-left min-w-[170px] transition-all hover:-translate-y-0.5 ${
        featured
          ? 'border-green shadow-[0_0_22px_rgba(0,232,123,0.1)]'
          : 'border-border hover:border-border-2'
      }`}
    >
      <div className="font-mono text-[22px] font-bold text-text-1">{price}</div>
      <div className="font-mono text-[9px] text-text-3 mb-[9px]">{period}</div>
      <ul className="flex flex-col gap-1">
        {features.map((f, i) => (
          <li key={i} className="text-[10.5px] text-text-2 flex items-center gap-1">
            <span className="text-green font-mono text-[8px]">✓</span>
            {f}
          </li>
        ))}
      </ul>
      <button
        className={`mt-[11px] w-full py-[7px] rounded-md font-mono text-[10px] font-semibold transition-all ${
          featured
            ? 'bg-green text-bg hover:shadow-[0_0_14px_rgba(0,232,123,0.2)]'
            : 'bg-transparent text-text-2 border border-border'
        }`}
      >
        {label || (featured ? 'Commencer' : 'Débloquer')}
      </button>
    </div>
  );
}

// =============================================================================
// MATCH ANALYSIS MODAL
// =============================================================================

// Helper to calculate edge and kelly from model prob and odds
function calcEdgeKelly(modelProb: number, odds: number | null | undefined): { edge: number; kelly: number } {
  if (!odds || odds <= 1) return { edge: 0, kelly: 0 };
  const bookProb = 1 / odds;
  const edge = ((modelProb - bookProb) / bookProb) * 100;
  const kelly = edge > 0 ? ((modelProb * odds - 1) / (odds - 1)) * 0.5 * 100 : 0; // Kelly/2
  return { edge, kelly: Math.max(0, kelly) };
}

// Color coding based on edge value
function getEdgeColor(edge: number): string {
  if (edge >= 10) return 'text-green'; // Excellent
  if (edge >= 5) return 'text-cyan';   // Good
  if (edge >= 0) return 'text-text-2'; // Neutral
  return 'text-red';                   // Negative
}

function MatchAnalysisModal({
  analysis,
  loading,
  onClose,
}: {
  analysis: MatchAnalysisResponse | null;
  loading: boolean;
  onClose: () => void;
}) {
  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div className="bg-bg-2 border border-border rounded-xl p-8 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-green border-t-transparent rounded-full mx-auto mb-4" />
          <span className="font-mono text-sm text-text-2">Chargement de l'analyse...</span>
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  const { match, has_access } = analysis;

  // Format kickoff
  const kickoffDate = new Date(match.kickoff + 'Z');
  const dateStr = kickoffDate.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Paris',
  });

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-bg-2 border border-border rounded-xl w-full max-w-5xl my-8 relative">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-bg-3 border border-border text-text-2 hover:text-text-1 hover:border-border-2 transition-all flex items-center justify-center z-10"
        >
          ✕
        </button>

        {/* Header */}
        <div className="p-6 border-b border-border">
          <div className="font-mono text-[8px] text-green tracking-[3px] uppercase mb-2">
            Analyse Dixon-Coles
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              {match.home_team.logo_url && (
                <img src={match.home_team.logo_url} alt="" className="w-10 h-10 object-contain" />
              )}
              <span className="text-xl font-bold text-text-1">{match.home_team.name}</span>
            </div>
            <span className="text-text-3 font-mono">vs</span>
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold text-text-1">{match.away_team.name}</span>
              {match.away_team.logo_url && (
                <img src={match.away_team.logo_url} alt="" className="w-10 h-10 object-contain" />
              )}
            </div>
          </div>
          <div className="mt-2 font-mono text-xs text-text-3">
            {match.competition} · J{match.matchday} · {dateStr}
          </div>
        </div>

        {has_access && analysis.analysis ? (
          <div className="p-6 space-y-6">
            {/* ============================================= */}
            {/* RECOMMENDATIONS - TOP PROMINENT SECTION */}
            {/* ============================================= */}
            {analysis.edges && analysis.edges.some(e => e.edge_percentage >= 5) && (
              <div className="bg-gradient-to-br from-green-dark via-[#0a1a12] to-bg-2 border-2 border-green/50 rounded-xl p-5 shadow-[0_0_30px_rgba(0,232,123,0.15)]">
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-3 h-3 rounded-full bg-green animate-pulse shadow-[0_0_10px_rgba(0,232,123,0.5)]" />
                  <h2 className="font-mono text-sm text-green uppercase tracking-[3px] font-bold">
                    Paris Recommandés
                  </h2>
                  <span className="ml-auto font-mono text-[9px] text-green/70 bg-green/10 px-2 py-1 rounded">
                    Edge ≥ 5%
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {analysis.edges?.filter(e => e.edge_percentage >= 5).map((edge, i) => (
                    <div
                      key={i}
                      className="bg-bg/60 backdrop-blur border border-green/30 rounded-lg p-4 hover:border-green/60 transition-all hover:shadow-[0_0_15px_rgba(0,232,123,0.1)]"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                          <div className="font-bold text-text-1 text-sm mb-1">{edge.market_display}</div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <RiskBadge level={edge.risk_level} />
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-2xl font-bold text-cyan">{edge.best_odds.toFixed(2)}</div>
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-border/50 grid grid-cols-4 gap-2">
                        <div>
                          <div className="font-mono text-[8px] text-text-3 uppercase">Prob.</div>
                          <div className="font-mono text-sm font-bold text-text-1">{edge.model_probability.toFixed(1)}%</div>
                        </div>
                        <div>
                          <div className="font-mono text-[8px] text-text-3 uppercase">Book</div>
                          <div className="font-mono text-sm font-semibold text-text-2">{edge.bookmaker_probability.toFixed(1)}%</div>
                        </div>
                        <div>
                          <div className="font-mono text-[8px] text-text-3 uppercase">Edge</div>
                          <div className="font-mono text-sm font-bold text-green">+{edge.edge_percentage.toFixed(1)}%</div>
                        </div>
                        <div>
                          <div className="font-mono text-[8px] text-text-3 uppercase">Kelly</div>
                          <div className="font-mono text-sm font-bold text-amber">{edge.kelly_stake.toFixed(1)}%</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Expected Goals */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <XGCard
                label={match.home_team.short_name || match.home_team.name}
                value={analysis.analysis.expected_goals.home}
                color="cyan"
              />
              <XGCard label="Total xG" value={analysis.analysis.expected_goals.total} color="green" />
              <XGCard
                label={match.away_team.short_name || match.away_team.name}
                value={analysis.analysis.expected_goals.away}
                color="amber"
              />
            </div>

            {/* ============================================= */}
            {/* ALL MARKETS TABLE WITH FULL STATS */}
            {/* ============================================= */}
            <div className="border-t border-border pt-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-mono text-[10px] text-text-3 uppercase tracking-[2px] flex items-center gap-2">
                  Tous les marchés · Probabilités & Edges
                </h3>
                <span className="font-mono text-[9px] text-text-3 bg-bg-3 px-2 py-1 rounded border border-border">
                  — = pas de cote bookmaker disponible
                </span>
              </div>
            </div>

            {/* Main Markets Table */}
            <div className="bg-bg-3 border border-border rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-bg-2">
                    <tr className="text-text-3 font-mono text-[9px] uppercase">
                      <th className="text-left py-3 px-3">Marché</th>
                      <th className="text-center py-3 px-2 w-20">Prob.</th>
                      <th className="text-center py-3 px-2 w-16">Cote</th>
                      <th className="text-center py-3 px-2 w-16">Edge</th>
                      <th className="text-center py-3 px-2 w-16">Kelly</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* 1X2 Section */}
                    <tr className="bg-bg-2/50">
                      <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                        Résultat 1X2
                      </td>
                    </tr>
                    <MarketRow
                      label="Victoire domicile"
                      prob={analysis.analysis.probabilities['1x2'].home_win * 100}
                      odds={analysis.odds?.home_win}
                    />
                    <MarketRow
                      label="Match nul"
                      prob={analysis.analysis.probabilities['1x2'].draw * 100}
                      odds={analysis.odds?.draw}
                    />
                    <MarketRow
                      label="Victoire extérieur"
                      prob={analysis.analysis.probabilities['1x2'].away_win * 100}
                      odds={analysis.odds?.away_win}
                    />

                    {/* Over/Under Section */}
                    <tr className="bg-bg-2/50">
                      <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                        Total Buts
                      </td>
                    </tr>
                    <MarketRow
                      label="Plus de 1.5 buts"
                      prob={analysis.analysis.probabilities.over_under['over_1.5'] * 100}
                      odds={null}
                    />
                    <MarketRow
                      label="Plus de 2.5 buts"
                      prob={analysis.analysis.probabilities.over_under['over_2.5'] * 100}
                      odds={analysis.odds?.over_25}
                    />
                    <MarketRow
                      label="Plus de 3.5 buts"
                      prob={analysis.analysis.probabilities.over_under['over_3.5'] * 100}
                      odds={null}
                    />
                    <MarketRow
                      label="Moins de 2.5 buts"
                      prob={analysis.analysis.probabilities.over_under['under_2.5'] * 100}
                      odds={analysis.odds?.under_25}
                    />

                    {/* BTTS Section */}
                    <tr className="bg-bg-2/50">
                      <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                        Les 2 équipes marquent (BTTS)
                      </td>
                    </tr>
                    <MarketRow
                      label="Les 2 équipes marquent"
                      prob={analysis.analysis.probabilities.btts.btts_yes * 100}
                      odds={analysis.odds?.btts_yes}
                    />
                    <MarketRow
                      label="Les 2 ne marquent pas"
                      prob={analysis.analysis.probabilities.btts.btts_no * 100}
                      odds={analysis.odds?.btts_no}
                    />

                    {/* Double Chance */}
                    {analysis.analysis.double_chance && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Double Chance
                          </td>
                        </tr>
                        <MarketRow label="1X (Dom ou Nul)" prob={analysis.analysis.double_chance['1x']} odds={null} />
                        <MarketRow label="X2 (Nul ou Ext)" prob={analysis.analysis.double_chance['x2']} odds={null} />
                        <MarketRow label="12 (Dom ou Ext)" prob={analysis.analysis.double_chance['12']} odds={null} />
                      </>
                    )}

                    {/* Draw No Bet */}
                    {analysis.analysis.draw_no_bet && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Draw No Bet
                          </td>
                        </tr>
                        <MarketRow label="DNB Domicile" prob={analysis.analysis.draw_no_bet.home} odds={null} />
                        <MarketRow label="DNB Extérieur" prob={analysis.analysis.draw_no_bet.away} odds={null} />
                      </>
                    )}

                    {/* Clean Sheet */}
                    {analysis.analysis.clean_sheet && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Clean Sheet
                          </td>
                        </tr>
                        <MarketRow label={`${match.home_team.short_name || match.home_team.name} Clean Sheet`} prob={analysis.analysis.clean_sheet.home} odds={null} />
                        <MarketRow label={`${match.away_team.short_name || match.away_team.name} Clean Sheet`} prob={analysis.analysis.clean_sheet.away} odds={null} />
                      </>
                    )}

                    {/* Win to Nil */}
                    {analysis.analysis.win_to_nil && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Victoire sans encaisser
                          </td>
                        </tr>
                        <MarketRow label={`${match.home_team.short_name || match.home_team.name} gagne à 0`} prob={analysis.analysis.win_to_nil.home} odds={null} />
                        <MarketRow label={`${match.away_team.short_name || match.away_team.name} gagne à 0`} prob={analysis.analysis.win_to_nil.away} odds={null} />
                      </>
                    )}

                    {/* Team Scores */}
                    {analysis.analysis.team_scores && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Équipe marque
                          </td>
                        </tr>
                        <MarketRow label={`${match.home_team.short_name || match.home_team.name} marque`} prob={analysis.analysis.team_scores.home} odds={null} />
                        <MarketRow label={`${match.away_team.short_name || match.away_team.name} marque`} prob={analysis.analysis.team_scores.away} odds={null} />
                      </>
                    )}

                    {/* Team Overs */}
                    {analysis.analysis.team_overs && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Buts par équipe
                          </td>
                        </tr>
                        <MarketRow label={`${match.home_team.short_name || match.home_team.name} +0.5 buts`} prob={analysis.analysis.team_overs.home_o05} odds={null} />
                        <MarketRow label={`${match.home_team.short_name || match.home_team.name} +1.5 buts`} prob={analysis.analysis.team_overs.home_o15} odds={null} />
                        <MarketRow label={`${match.away_team.short_name || match.away_team.name} +0.5 buts`} prob={analysis.analysis.team_overs.away_o05} odds={null} />
                        <MarketRow label={`${match.away_team.short_name || match.away_team.name} +1.5 buts`} prob={analysis.analysis.team_overs.away_o15} odds={null} />
                      </>
                    )}

                    {/* Odd/Even */}
                    {analysis.analysis.odd_even && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Pair/Impair
                          </td>
                        </tr>
                        <MarketRow label="Total Impair" prob={analysis.analysis.odd_even.odd} odds={null} />
                        <MarketRow label="Total Pair" prob={analysis.analysis.odd_even.even} odds={null} />
                      </>
                    )}

                    {/* Margin Home */}
                    {analysis.analysis.margin_home && (
                      <>
                        <tr className="bg-bg-2/50">
                          <td colSpan={5} className="py-2 px-3 font-mono text-[9px] text-cyan uppercase tracking-wider font-bold">
                            Marge de victoire {match.home_team.short_name || match.home_team.name}
                          </td>
                        </tr>
                        <MarketRow label="Gagne par 1 but" prob={analysis.analysis.margin_home.by_1} odds={null} />
                        <MarketRow label="Gagne par 2 buts" prob={analysis.analysis.margin_home.by_2} odds={null} />
                        <MarketRow label="Gagne par 3+ buts" prob={analysis.analysis.margin_home.by_3_plus} odds={null} />
                      </>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Exact Goals Grids */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Exact Total Goals */}
              {analysis.analysis.exact_totals && (
                <div className="bg-bg-3 border border-border rounded-lg p-4">
                  <h3 className="font-mono text-[10px] text-text-3 uppercase tracking-wider mb-3">
                    Nombre exact de buts total
                  </h3>
                  <div className="grid grid-cols-7 gap-1">
                    {Object.entries(analysis.analysis.exact_totals).map(([goals, prob]) => (
                      <div key={goals} className="bg-bg border border-border rounded p-2 text-center hover:border-cyan/30 transition-all">
                        <div className="font-mono text-sm font-bold text-text-1">{goals}</div>
                        <div className="font-mono text-[10px] text-cyan">{prob.toFixed(1)}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Home Exact Goals */}
              {analysis.analysis.home_exact_goals && (
                <div className="bg-bg-3 border border-border rounded-lg p-4">
                  <h3 className="font-mono text-[10px] text-text-3 uppercase tracking-wider mb-3">
                    Buts {match.home_team.short_name || match.home_team.name}
                  </h3>
                  <div className="grid grid-cols-5 gap-1">
                    {Object.entries(analysis.analysis.home_exact_goals).map(([goals, prob]) => (
                      <div key={goals} className="bg-bg border border-border rounded p-2 text-center">
                        <div className="font-mono text-sm font-bold text-text-1">{goals}</div>
                        <div className="font-mono text-[10px] text-green">{prob.toFixed(1)}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Away Exact Goals */}
              {analysis.analysis.away_exact_goals && (
                <div className="bg-bg-3 border border-border rounded-lg p-4">
                  <h3 className="font-mono text-[10px] text-text-3 uppercase tracking-wider mb-3">
                    Buts {match.away_team.short_name || match.away_team.name}
                  </h3>
                  <div className="grid grid-cols-5 gap-1">
                    {Object.entries(analysis.analysis.away_exact_goals).map(([goals, prob]) => (
                      <div key={goals} className="bg-bg border border-border rounded p-2 text-center">
                        <div className="font-mono text-sm font-bold text-text-1">{goals}</div>
                        <div className="font-mono text-[10px] text-amber">{prob.toFixed(1)}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Top 10 Exact Scores */}
            {analysis.analysis.exact_scores && analysis.analysis.exact_scores.length > 0 && (
              <div className="bg-bg-3 border border-border rounded-lg p-4">
                <h3 className="font-mono text-[10px] text-text-3 uppercase tracking-wider mb-3">
                  Top 10 scores exacts
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  {analysis.analysis.exact_scores.map((es, i) => (
                    <div
                      key={i}
                      className="bg-bg border border-border rounded-lg p-3 text-center hover:border-green/30 transition-all"
                    >
                      <div className="font-mono text-lg font-bold text-text-1">{es.score}</div>
                      <div className="font-mono text-xs text-green">{(es.probability * 100).toFixed(1)}%</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Score Matrix */}
            {analysis.analysis.score_matrix && analysis.analysis.score_matrix.length > 0 && (
              <div className="bg-bg-3 border border-border rounded-lg p-4">
                <h3 className="font-mono text-[10px] text-text-3 uppercase tracking-wider mb-3">
                  Matrice des scores (probabilités)
                </h3>
                <ScoreMatrix matrix={analysis.analysis.score_matrix} />
              </div>
            )}

            {/* Color Legend */}
            <div className="flex items-center gap-6 justify-center pt-4 border-t border-border">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-green" />
                <span className="font-mono text-[9px] text-text-3">Edge ≥10%</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-cyan" />
                <span className="font-mono text-[9px] text-text-3">Edge 5-10%</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-text-2" />
                <span className="font-mono text-[9px] text-text-3">Edge 0-5%</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-red" />
                <span className="font-mono text-[9px] text-text-3">Edge &lt;0%</span>
              </div>
            </div>
          </div>
        ) : (
          /* Preview for non-subscribers */
          <div className="p-6 text-center">
            {analysis.preview && (
              <div className="mb-6">
                <div className="text-4xl font-bold text-green mb-2">
                  +{analysis.preview.best_edge}%
                </div>
                <div className="text-text-2">
                  Meilleur edge détecté · {analysis.preview.edges_count} opportunités
                </div>
                <div className="text-text-3 font-mono text-sm mt-2">
                  xG total estimé: {analysis.preview.expected_goals_total}
                </div>
              </div>
            )}
            <div className="bg-bg-3 border border-border rounded-lg p-6 max-w-md mx-auto">
              <div className="text-lg font-bold text-text-1 mb-2">
                {analysis.message || "Abonnez-vous pour voir l'analyse complète"}
              </div>
              <button className="mt-4 bg-green text-bg font-mono text-sm font-semibold px-6 py-2 rounded-lg hover:shadow-[0_0_14px_rgba(0,232,123,0.3)] transition-all">
                Débloquer l'analyse
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Market Row Component - shows prob, odds, edge, kelly with color coding
function MarketRow({ label, prob, odds }: { label: string; prob: number; odds: number | null | undefined }) {
  const { edge, kelly } = calcEdgeKelly(prob / 100, odds);
  const edgeColor = getEdgeColor(edge);
  const hasOdds = odds && odds > 1;

  return (
    <tr className={`border-t border-border/50 hover:bg-bg-2/30 transition-colors ${edge >= 5 ? 'bg-green/5' : ''}`}>
      <td className="py-2 px-3 text-text-1 text-[12px]">{label}</td>
      <td className="py-2 px-2 text-center">
        <span className="font-mono text-[12px] text-text-1 font-semibold">{prob.toFixed(1)}%</span>
      </td>
      <td className="py-2 px-2 text-center">
        {hasOdds ? (
          <span className="font-mono text-[12px] text-cyan font-bold">{odds.toFixed(2)}</span>
        ) : (
          <span className="font-mono text-[10px] text-text-3">—</span>
        )}
      </td>
      <td className="py-2 px-2 text-center">
        {hasOdds ? (
          <span className={`font-mono text-[12px] font-bold ${edgeColor}`}>
            {edge >= 0 ? '+' : ''}{edge.toFixed(1)}%
          </span>
        ) : (
          <span className="font-mono text-[10px] text-text-3">—</span>
        )}
      </td>
      <td className="py-2 px-2 text-center">
        {hasOdds && kelly > 0 ? (
          <span className="font-mono text-[12px] text-amber font-semibold">{kelly.toFixed(1)}%</span>
        ) : (
          <span className="font-mono text-[10px] text-text-3">—</span>
        )}
      </td>
    </tr>
  );
}

// Helper Components for Modal
function XGCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorClasses: Record<string, string> = {
    cyan: 'text-cyan border-cyan/30',
    green: 'text-green border-green/30',
    amber: 'text-amber border-amber/30',
  };
  return (
    <div className={`bg-bg-3 border rounded-lg p-4 text-center ${colorClasses[color] || 'border-border'}`}>
      <div className="font-mono text-[10px] text-text-3 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-mono text-3xl font-bold ${colorClasses[color]?.split(' ')[0] || 'text-text-1'}`}>
        {value.toFixed(2)}
      </div>
      <div className="font-mono text-[9px] text-text-3 mt-1">xG</div>
    </div>
  );
}

function ScoreMatrix({ matrix }: { matrix: number[][] }) {
  const maxGoals = Math.min(matrix.length, 6); // Limit to 6x6

  return (
    <div className="overflow-x-auto">
      <table className="min-w-[300px] mx-auto">
        <thead>
          <tr>
            <th className="w-8 h-8"></th>
            {Array.from({ length: maxGoals }).map((_, i) => (
              <th key={i} className="w-10 h-8 font-mono text-[10px] text-text-3 text-center">
                {i}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: maxGoals }).map((_, homeGoals) => (
            <tr key={homeGoals}>
              <td className="font-mono text-[10px] text-text-3 text-center">{homeGoals}</td>
              {Array.from({ length: maxGoals }).map((_, awayGoals) => {
                const prob = matrix[homeGoals]?.[awayGoals] || 0;
                const intensity = Math.min(prob * 8, 1); // Scale for visibility
                const bgColor =
                  homeGoals > awayGoals
                    ? `rgba(0, 232, 123, ${intensity})`
                    : homeGoals < awayGoals
                    ? `rgba(255, 186, 0, ${intensity})`
                    : `rgba(150, 150, 150, ${intensity})`;
                return (
                  <td
                    key={awayGoals}
                    className="w-10 h-10 text-center font-mono text-[9px] border border-border/30 rounded"
                    style={{ backgroundColor: bgColor }}
                  >
                    {(prob * 100).toFixed(1)}%
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex justify-center gap-4 mt-2 font-mono text-[9px] text-text-3">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-green/50" /> Victoire Dom
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-text-2/50" /> Nul
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-amber/50" /> Victoire Ext
        </span>
      </div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    safe: 'bg-green-dark text-green',
    medium: 'bg-amber-dark text-amber',
    risky: 'bg-red-dark text-red',
  };
  const labels: Record<string, string> = {
    safe: 'SÛR',
    medium: 'MOYEN',
    risky: 'RISQUÉ',
  };
  return (
    <span className={`font-mono text-[8px] font-bold px-2 py-0.5 rounded ${colors[level] || colors.medium}`}>
      {labels[level] || level}
    </span>
  );
}
