'use client';

import { useState, useEffect } from 'react';
import { getOpportunities, OpportunityResponse } from '@/lib/api';

type RiskFilter = 'all' | 'safe' | 'medium' | 'risky';

export default function DashboardPage() {
  const [filter, setFilter] = useState<RiskFilter>('all');
  const [opportunities, setOpportunities] = useState<OpportunityResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [freePreviewCount, setFreePreviewCount] = useState(3);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchOpportunities() {
      console.log("[Dashboard] Fetching opportunities...");
      try {
        setLoading(true);
        setError(null);
        const data = await getOpportunities({
          min_edge: 5,
          risk_level: filter === 'all' ? undefined : filter,
          limit: 20,
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
  }, [filter]);

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
        <div className="flex gap-[3px]">
          <TabButton active>Ligue 1</TabButton>
          <TabButton>Ligue 2</TabButton>
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
            <OpportunityCard key={opp.id} opportunity={opp} index={idx} />
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
    </div>
  );
}

// =============================================================================
// COMPONENTS
// =============================================================================

function TabButton({ children, active }: { children: React.ReactNode; active?: boolean }) {
  return (
    <button
      className={`font-mono text-[10px] px-[11px] py-1.5 rounded border transition-all ${
        active
          ? 'bg-green-dark border-green text-green'
          : 'bg-transparent border-border text-text-2 hover:border-border-2 hover:text-text-1'
      }`}
    >
      {children}
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

function OpportunityCard({ opportunity: opp, index }: { opportunity: OpportunityResponse; index: number }) {
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

        {/* Right side - Odds */}
        <div className="flex flex-col items-center justify-center min-w-[80px] py-2 px-3 bg-[rgba(255,255,255,0.015)] rounded-lg border border-border">
          <span className="font-mono text-[7.5px] text-text-3 uppercase tracking-[1.2px] mb-0.5">
            Cote
          </span>
          <span className="font-mono text-[24px] font-bold text-cyan leading-none">
            {opp.best_odds.toFixed(2)}
          </span>
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
