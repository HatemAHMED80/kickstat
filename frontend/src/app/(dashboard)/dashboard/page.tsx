'use client';

import { useState } from 'react';

// Types
interface Opportunity {
  id: number;
  match: string;
  matchDate: string;
  bet: string;
  modelProb: number;
  edge: number;
  odds: number;
  risk: 'safe' | 'medium' | 'risky';
  type?: 'combo';
  legs?: string[];
}

// Mock data - Replace with API calls
const MOCK_OPPORTUNITIES: Opportunity[] = [
  {
    id: 1,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'Victoire du PSG',
    modelProb: 62,
    edge: 13,
    odds: 2.04,
    risk: 'safe',
  },
  {
    id: 2,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'Plus de 1.5 buts',
    modelProb: 81,
    edge: 7,
    odds: 1.35,
    risk: 'safe',
  },
  {
    id: 3,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'Plus de 9.5 corners',
    modelProb: 64,
    edge: 9,
    odds: 1.82,
    risk: 'safe',
  },
  {
    id: 4,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'PSG mène à la mi-temps et gagne',
    modelProb: 41,
    edge: 9,
    odds: 3.13,
    risk: 'medium',
  },
  {
    id: 5,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'Gonçalo Ramos marque',
    modelProb: 42,
    edge: 8,
    odds: 2.90,
    risk: 'medium',
  },
  {
    id: 6,
    match: 'Lens vs Lille',
    matchDate: 'Sam. 19h',
    bet: 'Match nul dans le derby',
    modelProb: 28,
    edge: 7,
    odds: 4.75,
    risk: 'medium',
  },
  {
    id: 7,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'PSG gagne + Plus de 1.5 buts',
    modelProb: 56,
    edge: 16,
    odds: 2.50,
    risk: 'safe',
    type: 'combo',
    legs: ['Victoire PSG · 62%', 'Over 1.5 · 81%'],
  },
  {
    id: 8,
    match: 'PSG vs OM',
    matchDate: 'Sam. 21h',
    bet: 'PSG -1 + Over 2.5 + Ramos + BTTS Non',
    modelProb: 5.8,
    edge: 18,
    odds: 42.5,
    risk: 'risky',
    type: 'combo',
    legs: ['PSG -1 · 39%', 'Over 2.5 · 58%', 'Ramos BM · 42%', 'BTTS Non · 53%'],
  },
];

type RiskFilter = 'all' | 'safe' | 'medium' | 'risky';

export default function DashboardPage() {
  const [filter, setFilter] = useState<RiskFilter>('all');

  const filteredOpps = filter === 'all'
    ? MOCK_OPPORTUNITIES
    : MOCK_OPPORTUNITIES.filter(o => o.risk === filter);

  const counts = {
    all: MOCK_OPPORTUNITIES.length,
    safe: MOCK_OPPORTUNITIES.filter(o => o.risk === 'safe').length,
    medium: MOCK_OPPORTUNITIES.filter(o => o.risk === 'medium').length,
    risky: MOCK_OPPORTUNITIES.filter(o => o.risk === 'risky').length,
  };

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[12px] font-semibold text-text-2 tracking-wider uppercase flex items-center gap-[7px]">
          <span className="w-[3px] h-3 bg-green rounded" />
          Meilleures opportunités — J21
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

      {/* Opportunities list */}
      <div className="flex flex-col gap-1.5 mb-7">
        {filteredOpps.map((opp, idx) => (
          <OpportunityCard key={opp.id} opportunity={opp} index={idx} />
        ))}
      </div>

      {/* Locked banner */}
      <div className="bg-bg-3 border border-border rounded-[10px] py-3.5 px-[18px] flex items-center justify-center gap-2.5 flex-wrap">
        <span className="font-mono text-[11px] text-text-2">
          🔒 6 opportunités supplémentaires
        </span>
        <button className="font-mono text-[10px] px-3.5 py-1.5 rounded bg-green text-bg font-semibold hover:shadow-[0_0_14px_rgba(0,232,123,0.2)] transition-all">
          9,99€/mois → Tout voir
        </button>
        <button className="font-mono text-[10px] px-3.5 py-1.5 rounded bg-transparent text-text-2 font-semibold border border-border hover:border-border-2 hover:text-text-1 transition-all">
          0,99€ par match
        </button>
      </div>

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

function OpportunityCard({ opportunity: opp, index }: { opportunity: Opportunity; index: number }) {
  const riskColors = {
    safe: { text: 'text-green', bg: 'bg-green-dark', border: 'border-l-green' },
    medium: { text: 'text-amber', bg: 'bg-amber-dark', border: 'border-l-amber' },
    risky: { text: 'text-red', bg: 'bg-red-dark', border: 'border-l-red' },
  };

  const colors = riskColors[opp.risk];
  const confFillColors = {
    safe: 'bg-green',
    medium: 'bg-amber',
    risky: 'bg-red',
  };

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
              {opp.risk === 'safe' ? 'SÛR' : opp.risk === 'medium' ? 'MOYEN' : 'RISQUÉ'}
            </span>
            {opp.type === 'combo' && (
              <span className="font-mono text-[8px] text-text-3 bg-[rgba(255,255,255,0.03)] px-1.5 py-0.5 rounded">
                Combiné
              </span>
            )}
            <span className="font-mono text-[9px] text-text-3 tracking-wide">
              {opp.match} · {opp.matchDate}
            </span>
          </div>

          {/* Bet description */}
          <div className="text-[15px] font-bold text-text-1 tracking-tight leading-snug">
            {opp.bet}
          </div>

          {/* Confidence bar */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-[8.5px] text-text-3 uppercase tracking-wider min-w-[68px]">
              Notre modèle
            </span>
            <div className="flex-1 max-w-[180px] h-1.5 bg-border rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${confFillColors[opp.risk]}`}
                style={{ width: `${opp.modelProb}%` }}
              />
            </div>
            <span className={`font-mono text-[11px] font-semibold min-w-[32px] ${colors.text}`}>
              {opp.modelProb}%
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
                style={{ width: `${Math.min(opp.edge * 5, 100)}%` }}
              />
            </div>
            <span className="font-mono text-[10.5px] font-semibold text-green">
              +{opp.edge}%
            </span>
          </div>

          {/* Combo legs */}
          {opp.legs && (
            <div className="flex flex-wrap gap-1 mt-0.5">
              {opp.legs.map((leg, i) => (
                <span
                  key={i}
                  className="font-mono text-[9px] text-text-2 bg-[rgba(255,255,255,0.025)] border border-border rounded px-[7px] py-0.5"
                >
                  {leg}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Right side - Odds */}
        <div className="flex flex-col items-center justify-center min-w-[80px] py-2 px-3 bg-[rgba(255,255,255,0.015)] rounded-lg border border-border">
          <span className="font-mono text-[7.5px] text-text-3 uppercase tracking-[1.2px] mb-0.5">
            {opp.type === 'combo' ? 'Cote combinée' : 'Cote'}
          </span>
          <span className="font-mono text-[24px] font-bold text-cyan leading-none">
            {opp.odds}
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
