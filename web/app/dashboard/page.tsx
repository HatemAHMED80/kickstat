'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import MatchCard from '../components/MatchCard';
import { mockPredictions } from './mock-data';

// Type definitions
interface BanditRecommendation {
  market: string;
  confidence: number;
  segment: string;
  scores: { [key: string]: number };
}

interface Prediction {
  match_id: string;
  league: string;
  league_slug?: string;
  home_team: string;
  away_team: string;
  kickoff: string;
  model_probs: { home: number; draw: number; away: number };
  best_odds: { home: number; draw: number; away: number; [key: string]: number };
  bookmaker: { home: string; draw: string; away: string; [key: string]: string };
  edge: { home: number; draw: number; away: number; [key: string]: number };
  recommended_bet: string | null;
  kelly_stake: number;
  segment: string;
  quality_score?: number | null;
  confidence_badge?: string | null;
  is_european?: boolean;
  prediction_source?: string;
  bandit_recommendation?: BanditRecommendation | null;
  over_under_15?: { over_15: number; under_15: number } | null;
  over_under_15_edge?: { over_15: number; under_15: number } | null;
  over_under?: { over_25: number; under_25: number } | null;
  over_under_edge?: { over_25: number; under_25: number } | null;
  over_under_35?: { over_35: number; under_35: number } | null;
  over_under_35_edge?: { over_35: number; under_35: number } | null;
  btts?: { yes: number; no: number } | null;
  correct_score?: { [key: string]: number } | null;
  double_chance?: { '1x': number; 'x2': number; '12': number } | null;
  draw_no_bet?: { home: number | null; away: number | null } | null;
  spreads?: { home_m15: number | null; home_m25: number | null } | null;
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
  tier?: string;
  tier_label?: string;
  tier_emoji?: string;
}

// No mock data - we want to see real errors if API fails

// Backtest performance data (from full pipeline backtest on 1780 PL matches, away disabled)
const PIPELINE_STATS = {
  matches_tested: 1660,
  seasons: '2021-2025',
  configs: [
    { name: 'DC + ELO', roi: -2.8, bets: 627, accuracy: 53.6, ece: 0.0147 },
    { name: '+ XGBoost', roi: 0.2, bets: 1020, accuracy: 53.6, ece: 0.0078 },
    { name: '+ Calibration', roi: 1.7, bets: 1079, accuracy: 53.4, ece: 0.0078 },
    { name: '+ Bandit', roi: -0.6, bets: 662, accuracy: 53.4, ece: 0.0078 },
  ],
  features: 62,
  top_features: ['elo_diff', 'elo_away_prob', 'elo_home_prob', 'dc_home_prob', 'dominance_diff'],
  bandit_segments: 12,
};

export default function Dashboard() {
  const [selectedLeague, setSelectedLeague] = useState<string>('all');
  const [minEdge, setMinEdge] = useState<number>(3);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [combos, setCombos] = useState<Combo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string>('');
  const [showPipelineStats, setShowPipelineStats] = useState<boolean>(false);
  const [visibleCount, setVisibleCount] = useState<number>(12);
  const [selectedBadge, setSelectedBadge] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<'all' | 'simple' | 'combine'>('all');
  const [showRiskInfo, setShowRiskInfo] = useState<boolean>(false);

  // Get user email on mount (dashboard is public, no auth required)
  useEffect(() => {
    const email = localStorage.getItem('kickstat_user');
    if (email) {
      setUserEmail(email);
    }
  }, []);

  // Logout function
  const handleLogout = () => {
    localStorage.removeItem('kickstat_auth');
    localStorage.removeItem('kickstat_user');
    setUserEmail(''); // Clear email state to update UI
  };

  // Load real predictions from JSON file
  useEffect(() => {
    const fetchPredictions = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch('/predictions.json');

        if (!response.ok) {
          throw new Error('Failed to fetch predictions');
        }

        const data = await response.json();
        // Handle both old format (array) and new format ({predictions, combos})
        if (Array.isArray(data)) {
          setPredictions(data);
          setCombos([]);
        } else {
          setPredictions(data.predictions || []);
          setCombos(data.combos || []);
        }
        setLoading(false);
      } catch (err) {
        console.error('Error loading predictions:', err);
        setError('Unable to load predictions. Make sure to run: python generate_predictions_json.py');
        setLoading(false);
        // Fallback to mock data for development
        // @ts-ignore
        setPredictions(mockPredictions);
      }
    };

    fetchPredictions();
  }, []);

  const filteredPredictions = predictions.filter(pred => {
    if (selectedLeague !== 'all' && pred.league !== selectedLeague) return false;
    // reset pagination when filters change is handled via key on the list
    const allEdges = [
      pred.edge.home ?? 0,
      pred.edge.draw ?? 0,
      pred.edge.away ?? 0,
      pred.over_under_edge?.over_25 ?? 0,
      pred.over_under_edge?.under_25 ?? 0,
      pred.over_under_35_edge?.over_35 ?? 0,
      pred.over_under_35_edge?.under_35 ?? 0,
      pred.over_under_15_edge?.over_15 ?? 0,
      pred.over_under_15_edge?.under_15 ?? 0,
    ];
    const maxEdge = Math.max(...allEdges);
    if (maxEdge < minEdge) return false;
    if (selectedBadge !== 'all' && pred.confidence_badge !== selectedBadge) return false;
    return true;
  });

  const filteredCombos = selectedBadge === 'all'
    ? combos
    : combos.filter(c => c.confidence === selectedBadge);

  const BADGE_ORDER: Record<string, number> = {
    ULTRA_SAFE: 0, HIGH_SAFE: 1, SAFE: 2, VALUE: 3, RISKY: 4, ULTRA_RISKY: 5,
  };

  type RecoItem =
    | { kind: 'match'; data: Prediction }
    | { kind: 'combo'; data: Combo; rank: number };

  const unifiedRecommendations: RecoItem[] = [
    ...(selectedType !== 'combine' ? filteredPredictions.map(p => ({ kind: 'match' as const, data: p })) : []),
    ...(selectedType !== 'simple' ? filteredCombos.map((c, i) => ({ kind: 'combo' as const, data: c, rank: i + 1 })) : []),
  ].sort((a, b) => {
    // Primary: chronological order (combos have no kickoff, go last)
    const dateA = a.kind === 'match' ? new Date((a.data as Prediction).kickoff).getTime() : Infinity;
    const dateB = b.kind === 'match' ? new Date((b.data as Prediction).kickoff).getTime() : Infinity;
    if (dateA !== dateB) return dateA - dateB;
    // Secondary: badge quality within same kickoff
    const badgeA = a.kind === 'match' ? (a.data.confidence_badge ?? 'RISKY') : a.data.confidence;
    const badgeB = b.kind === 'match' ? (b.data.confidence_badge ?? 'RISKY') : b.data.confidence;
    return (BADGE_ORDER[badgeA] ?? 4) - (BADGE_ORDER[badgeB] ?? 4);
  });

  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      {/* Gradient background — same as landing page */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_80%_50%_at_20%_-10%,rgba(124,58,237,0.08),transparent),radial-gradient(ellipse_60%_40%_at_80%_60%,rgba(219,39,119,0.05),transparent)]" />

      {/* Navigation */}
      <nav className="relative z-50 border-b border-white/5 bg-[#09090b]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          <Link href="/" className="text-xl font-bold tracking-tight shrink-0">
            Kick<span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">stat</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <Link href="/dashboard" className="text-sm text-violet-400 font-semibold shrink-0">Dashboard</Link>
            <Link href="/historique" className="hidden sm:block text-sm text-gray-400 hover:text-white transition shrink-0">Historique</Link>
            {userEmail ? (
              <>
                <span className="hidden md:inline text-gray-500 text-sm truncate max-w-[140px]">{userEmail}</span>
                <button
                  onClick={handleLogout}
                  className="text-sm px-3 sm:px-4 py-2 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 transition shrink-0"
                >
                  <span className="hidden sm:inline">Déconnexion</span>
                  <span className="sm:hidden">×</span>
                </button>
              </>
            ) : (
              <Link
                href="/login"
                className="text-sm px-3 sm:px-4 py-2 rounded-lg bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white font-semibold transition shadow-lg shadow-violet-500/25 shrink-0"
              >
                Connexion
              </Link>
            )}
          </div>
        </div>
      </nav>

      {/* Header */}
      <div className="relative border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white">Paris du jour</h1>
            <span className="px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-mono uppercase tracking-widest animate-pulse">
              Live
            </span>
          </div>
          <p className="text-gray-600 font-mono text-sm mb-4">
            {new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </p>

          {/* Pipeline Badge */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/3 border border-white/8 text-xs font-mono">
              <span className="text-violet-400">Dixon-Coles</span>
              <span className="text-white/20">+</span>
              <span className="text-violet-400">ELO</span>
              <span className="text-white/20">+</span>
              <span className="text-fuchsia-400">XGBoost</span>
              <span className="text-white/20">+</span>
              <span className="text-fuchsia-400">Calibration</span>
              <span className="text-white/20">+</span>
              <span className="text-pink-400">Bandit</span>
            </div>
            <button
              onClick={() => setShowPipelineStats(!showPipelineStats)}
              className="px-3 py-1.5 rounded-full border border-white/8 text-gray-500 text-xs font-mono hover:border-violet-500/30 hover:text-violet-300 transition"
            >
              {showPipelineStats ? 'Masquer stats' : 'Voir performance'}
            </button>
            <Link
              href="/historique"
              className="px-3 py-1.5 rounded-full border border-violet-500/20 text-violet-400 text-xs font-mono hover:bg-violet-500/10 transition"
            >
              Historique des paris →
            </Link>
          </div>

          {/* Pipeline Performance Panel (collapsible) */}
          {showPipelineStats && (
            <div className="mt-6 p-5 bg-white/3 rounded-xl border border-white/8">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-sm font-bold text-transparent bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text">
                  Pipeline Performance
                </span>
                <span className="text-xs text-gray-600 font-mono">
                  ({PIPELINE_STATS.matches_tested} matchs | PL {PIPELINE_STATS.seasons})
                </span>
              </div>

              {/* ROI Progression */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                {PIPELINE_STATS.configs.map((config, idx) => (
                  <div
                    key={config.name}
                    className={`p-3 rounded-lg border ${
                      idx === PIPELINE_STATS.configs.length - 1
                        ? 'bg-violet-500/10 border-violet-500/30'
                        : 'bg-white/3 border-white/5'
                    }`}
                  >
                    <div className="text-xs text-gray-600 font-mono mb-1">{config.name}</div>
                    <div className={`text-xl font-bold font-mono ${
                      config.roi >= 0 ? 'text-violet-400' : 'text-red-400'
                    }`}>
                      {config.roi > 0 ? '+' : ''}{config.roi.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-700 font-mono mt-1">
                      {config.bets} paris | ECE {config.ece.toFixed(4)}
                    </div>
                  </div>
                ))}
              </div>

              {/* Features & Bandit Info */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3 bg-white/3 rounded-lg border border-white/5">
                  <div className="text-xs text-gray-600 font-mono mb-2">XGBoost ({PIPELINE_STATS.features} features)</div>
                  <div className="flex flex-wrap gap-1">
                    {PIPELINE_STATS.top_features.map((f) => (
                      <span key={f} className="px-2 py-0.5 rounded bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-mono">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="p-3 bg-white/3 rounded-lg border border-white/5">
                  <div className="text-xs text-gray-600 font-mono mb-2">Bandit Thompson ({PIPELINE_STATS.bandit_segments} segments)</div>
                  <div className="text-xs text-gray-500">
                    Filtre automatique des mauvais paris. Réduit les paris de 1946 à 1299 tout en améliorant le ROI de -2.6% à -2.2%.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="relative border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div>
              <label className="text-xs font-mono uppercase tracking-wider text-gray-600 mr-2">Ligue:</label>
              <select
                value={selectedLeague}
                onChange={(e) => { setSelectedLeague(e.target.value); setVisibleCount(12); }}
                className="px-4 py-2 border border-white/10 text-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 hover:border-violet-500/30 transition font-mono"
                style={{ backgroundColor: '#18181b' }}
              >
                <option value="all" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Toutes les ligues</option>
                <optgroup label="Top 5" style={{ backgroundColor: '#18181b', color: '#a1a1aa' }}>
                  <option value="Premier League" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Premier League</option>
                  <option value="Ligue 1" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Ligue 1</option>
                  <option value="La Liga" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>La Liga</option>
                  <option value="Bundesliga" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Bundesliga</option>
                  <option value="Serie A" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Serie A</option>
                </optgroup>
                <optgroup label="Européen" style={{ backgroundColor: '#18181b', color: '#a1a1aa' }}>
                  <option value="Champions League" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Champions League</option>
                  <option value="Europa League" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Europa League</option>
                  <option value="Conference League" style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>Conference League</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="text-xs font-mono uppercase tracking-wider text-gray-600 mr-2">Min Edge:</label>
              <select
                value={minEdge}
                onChange={(e) => { setMinEdge(Number(e.target.value)); setVisibleCount(12); }}
                className="px-4 py-2 border border-white/10 text-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 hover:border-violet-500/30 transition font-mono"
                style={{ backgroundColor: '#18181b' }}
              >
                <option value="0"  style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>0%+</option>
                <option value="3"  style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>3%+</option>
                <option value="5"  style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>5%+ (Recommandé)</option>
                <option value="8"  style={{ backgroundColor: '#18181b', color: '#e4e4e7' }}>8%+ (Haute valeur)</option>
              </select>
            </div>

            {/* Type de paris */}
            <div className="flex items-center gap-2">
              <label className="text-xs font-mono uppercase tracking-wider text-gray-600 mr-1">Type:</label>
              {([
                { key: 'all',     label: 'Tous' },
                { key: 'simple',  label: '1 Match' },
                { key: 'combine', label: 'Combiné' },
              ] as const).map(t => (
                <button
                  key={t.key}
                  onClick={() => { setSelectedType(t.key); setVisibleCount(12); }}
                  className={`px-3 py-1.5 rounded-full border text-xs font-bold transition ${
                    selectedType === t.key
                      ? 'bg-violet-500/20 text-violet-300 border-violet-400/60'
                      : 'border-white/8 text-gray-600 hover:text-violet-300 hover:border-violet-500/30'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Risk level filter pills */}
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs font-mono uppercase tracking-wider text-gray-600 mr-1">Risque:</label>
              <div className="relative">
                <button
                  onClick={() => setShowRiskInfo(v => !v)}
                  className="w-4 h-4 rounded-full bg-white/5 border border-white/10 text-gray-500 text-[10px] font-bold flex items-center justify-center hover:bg-violet-500/20 hover:border-violet-500/30 hover:text-violet-300 transition"
                  title="Explication des niveaux"
                >
                  i
                </button>
                {showRiskInfo && (
                  <>
                    {/* Backdrop — clic à côté ferme le panneau */}
                    <div className="fixed inset-0 z-40" onClick={() => setShowRiskInfo(false)} />
                    <div className="absolute left-0 top-6 z-50 w-72 bg-[#09090b] border border-white/10 rounded-xl shadow-2xl p-4 text-xs">
                      <div className="flex justify-between items-center mb-3">
                        <span className="font-bold text-white text-sm">Niveaux de risque</span>
                        <button onClick={() => setShowRiskInfo(false)} className="text-gray-500 hover:text-white transition text-base leading-none">×</button>
                      </div>
                      <div className="space-y-2.5">
                        {[
                          { icon: '🏆', label: 'ULTRA SAFE',   cls: 'text-yellow-300',  prob: '≥ 85%',    desc: 'Probabilité très élevée. Le favori écrasant du modèle.' },
                          { icon: '🛡️', label: 'HIGH SAFE',    cls: 'text-emerald-300', prob: '75–85%',   desc: 'Haute probabilité. Paris solide avec peu d\'incertitude.' },
                          { icon: '✅', label: 'SAFE',          cls: 'text-emerald-400', prob: '60–75%',   desc: 'Probabilité confortable. Bon équilibre risque/récompense.' },
                          { icon: '💎', label: 'VALUE',         cls: 'text-cyan-400',    prob: '50–60%',   desc: 'Légère faveur du modèle + edge sur les cotes.' },
                          { icon: '⚠️', label: 'RISQUÉ',        cls: 'text-orange-400',  prob: '35–50%',   desc: 'Incertain mais edge détecté. À jouer avec prudence.' },
                          { icon: '💀', label: 'ULTRA RISQUÉ',  cls: 'text-red-400',     prob: '< 35%',    desc: 'Très spéculatif. Cotes élevées, probabilité faible.' },
                        ].map(t => (
                          <div key={t.label} className="flex items-start gap-2">
                            <span className="text-base leading-none mt-0.5">{t.icon}</span>
                            <div>
                              <span className={`font-bold ${t.cls}`}>{t.label}</span>
                              <span className="text-gray-500 ml-1 font-mono">({t.prob})</span>
                              <p className="text-gray-400 mt-0.5">{t.desc}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 pt-3 border-t border-white/8 text-gray-600 text-[10px]">
                        La probabilité indique la confiance du modèle, pas une garantie de résultat.
                      </div>
                    </div>
                  </>
                )}
              </div>
              {[
                { key: 'all',        label: 'Tous',           style: selectedBadge === 'all'        ? 'bg-white/10 text-white border-white/20'                  : 'border-white/8 text-gray-600 hover:text-gray-300' },
                { key: 'ULTRA_SAFE', label: '🏆 Ultra',       style: selectedBadge === 'ULTRA_SAFE' ? 'bg-yellow-400/20 text-yellow-300 border-yellow-400/60'   : 'border-white/8 text-gray-600 hover:text-yellow-300' },
                { key: 'HIGH_SAFE',  label: '🛡️ High',        style: selectedBadge === 'HIGH_SAFE'  ? 'bg-emerald-400/20 text-emerald-300 border-emerald-400/60': 'border-white/8 text-gray-600 hover:text-emerald-300' },
                { key: 'SAFE',       label: '✅ Safe',         style: selectedBadge === 'SAFE'       ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50': 'border-white/8 text-gray-600 hover:text-emerald-400' },
                { key: 'VALUE',      label: '💎 Value',        style: selectedBadge === 'VALUE'      ? 'bg-violet-500/20 text-violet-400 border-violet-500/50'   : 'border-white/8 text-gray-600 hover:text-violet-400' },
                { key: 'RISKY',      label: '⚠️ Risqué',      style: selectedBadge === 'RISKY'      ? 'bg-orange-500/20 text-orange-400 border-orange-500/50'   : 'border-white/8 text-gray-600 hover:text-orange-400' },
                { key: 'ULTRA_RISKY',label: '💀 Ultra Risqué',style: selectedBadge === 'ULTRA_RISKY'? 'bg-red-600/20 text-red-400 border-red-500/60'             : 'border-white/8 text-gray-600 hover:text-red-400' },
              ].map(t => (
                <button
                  key={t.key}
                  onClick={() => { setSelectedBadge(t.key); setVisibleCount(12); }}
                  className={`px-3 py-1.5 rounded-full border text-xs font-bold transition ${t.style}`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-3">
              <span className="text-sm text-gray-600 font-mono">
                <span className="text-violet-400 font-bold">{unifiedRecommendations.length}</span> paris
              </span>
              <div className="h-2 w-2 rounded-full bg-violet-400 animate-pulse"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Unified Recommendations */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Loading State */}
        {loading && (
          <div className="text-center py-16">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-violet-500/20 border-t-violet-500 mb-4"></div>
            <p className="text-gray-400 font-semibold">Analyse en cours...</p>
            <p className="text-gray-600 text-sm mt-2 font-mono">Dixon-Coles + ELO + XGBoost (62 features) + Calibration + Bandit</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-red-900/20 border-2 border-red-500/50 rounded-lg p-6 mb-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 text-4xl">❌</div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-red-400 mb-2">Erreur de chargement</h3>
                <p className="text-red-300 text-sm mb-3">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Unified list: single bets + combos sorted by safety */}
        {!loading && (
          <>
            <div className="grid gap-6">
              {unifiedRecommendations.slice(0, visibleCount).map((item, idx) =>
                item.kind === 'match'
                  ? <MatchCard key={item.data.match_id} prediction={item.data} />
                  : <ComboCard key={item.data.combo_id + idx} combo={item.data} rank={item.rank} />
              )}
            </div>

            {visibleCount < unifiedRecommendations.length && (
              <div className="text-center mt-8">
                <button
                  onClick={() => setVisibleCount(v => v + 12)}
                  className="px-6 py-3 rounded-xl border border-white/8 text-gray-500 hover:border-violet-500/30 hover:text-violet-300 transition text-sm"
                >
                  Voir plus ({unifiedRecommendations.length - visibleCount} restants)
                </button>
              </div>
            )}

            {unifiedRecommendations.length === 0 && (
              <div className="text-center py-16">
                <div className="text-gray-700 text-5xl mb-4">📭</div>
                <p className="text-gray-400 text-lg font-semibold">Aucun paris ne correspond à tes filtres</p>
                <p className="text-gray-600 text-sm mt-2">Essaie un autre niveau de risque ou baisse le min edge</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* CTA */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-16">
        <div className="p-8 rounded-3xl border border-violet-500/20 bg-gradient-to-b from-violet-500/10 to-transparent text-center">
          <h3 className="text-2xl font-black mb-2">
            Prêt à parier
            <span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent"> intelligemment ?</span>
          </h3>
          <p className="text-gray-500 text-sm mb-6">Accès gratuit · Pas de carte bancaire · Prédictions chaque jour</p>
          <Link
            href="/"
            className="inline-block px-8 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold hover:from-violet-500 hover:to-fuchsia-500 transition shadow-xl shadow-violet-500/30"
          >
            En savoir plus →
          </Link>
        </div>
      </div>
    </div>
  );
}


// Format raw market keys into readable labels
function formatMarket(market: string | undefined): string {
  if (!market) return '';
  const map: Record<string, string> = {
    home:      '1 — Victoire dom.',
    draw:      'Match nul',
    away:      '2 — Victoire ext.',
    over15:    '+1,5 buts',
    under15:   '-1,5 buts',
    over25:    '+2,5 buts',
    under25:   '-2,5 buts',
    over35:    '+3,5 buts',
    under35:   '-3,5 buts',
    btts_yes:  'Les 2 équipes marquent — Oui',
    btts_no:   'Les 2 équipes marquent — Non',
    dc_1x:     'Double chance 1X',
    dc_x2:     'Double chance X2',
    dc_12:     'Double chance 12',
    dnb_home:  'Nul remboursé — Dom.',
    dnb_away:  'Nul remboursé — Ext.',
    spread_home_m15: 'Handicap -1,5 Dom.',
    spread_away_p15: 'Handicap +1,5 Ext.',
    spread_home_m25: 'Handicap -2,5 Dom.',
    spread_away_p25: 'Handicap +2,5 Ext.',
  };
  return map[market] ?? market;
}

// Combined Bet Card
const CONFIDENCE_TIERS: Record<string, { style: string; label: string; icon: string; border: string }> = {
  'ULTRA_SAFE': {
    style: 'from-yellow-300/20 to-amber-400/20 border-yellow-400/60 text-yellow-300',
    label: 'ULTRA SAFE',
    icon: '🏆',
    border: 'border-yellow-400/30',
  },
  'HIGH_SAFE': {
    style: 'from-emerald-400/20 to-green-400/20 border-emerald-400/60 text-emerald-300',
    label: 'HIGH SAFE',
    icon: '🛡️',
    border: 'border-emerald-500/30',
  },
  'SAFE': {
    style: 'from-emerald-500/20 to-emerald-600/20 border-emerald-500/50 text-emerald-400',
    label: 'SAFE',
    icon: '✅',
    border: 'border-emerald-500/20',
  },
  'VALUE': {
    style: 'from-cyan-500/20 to-blue-500/20 border-cyan-500/50 text-cyan-400',
    label: 'VALUE',
    icon: '💎',
    border: 'border-cyan-500/20',
  },
  'RISKY': {
    style: 'from-orange-500/20 to-red-500/20 border-orange-500/50 text-orange-400',
    label: 'RISKY',
    icon: '⚠️',
    border: 'border-orange-500/20',
  },
  'ULTRA_RISKY': {
    style: 'from-red-600/20 to-red-800/20 border-red-500/60 text-red-400',
    label: 'ULTRA RISQUÉ',
    icon: '💀',
    border: 'border-red-600/30',
  },
};

function ComboCard({ combo, rank }: { combo: Combo; rank: number }) {
  const tier = CONFIDENCE_TIERS[combo.confidence] || CONFIDENCE_TIERS['VALUE'];
  const legCount = combo.n_legs || combo.matches.length;

  return (
    <div className={`bg-white/3 rounded-xl border ${tier.border} hover:border-violet-500/30 transition overflow-hidden`}>

      {/* ── HEADER ─────────────────────────────────────────────── */}
      <div className="px-5 py-4 bg-white/3 border-b border-white/5">
        <div className="flex items-start justify-between gap-4">

          {/* Left: rank badge + confidence tier + type label */}
          <div className="flex flex-wrap items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-yellow-400/15 border border-yellow-400/40 flex items-center justify-center text-yellow-300 text-xs font-black shrink-0">
              {rank}
            </div>
            <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gradient-to-r ${tier.style} text-xs font-bold border shrink-0`}>
              {tier.icon} {tier.label}
            </span>
            <span className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400 text-xs font-mono shrink-0">
              {combo.type === 'same_match' ? 'Same Match' : `Combiné ${legCount} sélections`}
            </span>
          </div>

          {/* Right: combined odds — big and prominent */}
          <div className="text-right shrink-0">
            <div className="text-2xl font-black text-yellow-400 font-mono leading-none">{combo.combined_odds.toFixed(2)}</div>
            <div className="text-[10px] text-gray-500 font-mono mt-0.5 uppercase tracking-wider">Cote combinée</div>
          </div>
        </div>
      </div>

      {/* ── LEGS ───────────────────────────────────────────────── */}
      <div className="px-5 py-4 space-y-3">
        {combo.type === 'same_match' ? (
          /* Same Match */
          <div className="rounded-xl border border-violet-500/30 overflow-hidden">
            {/* Bet — EN PREMIER, gros et visible */}
            <div className="px-4 pt-4 pb-3 bg-gradient-to-r from-violet-600/20 to-fuchsia-600/10">
              <div className="text-[10px] text-violet-400 font-mono uppercase tracking-widest mb-1">✦ Pari conseillé</div>
              <div className="text-base font-black text-white leading-snug">{combo.label}</div>
            </div>
            {/* Match context — en dessous, plus petit */}
            <div className="flex items-center gap-3 px-4 py-2.5 bg-white/3 border-t border-white/5">
              <span className="text-fuchsia-400 text-xs">⚡</span>
              <div className="min-w-0">
                <div className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">{combo.matches[0]?.league}</div>
                <div className="text-xs text-gray-400 truncate">
                  {combo.matches[0]?.home_team} <span className="text-gray-600">vs</span> {combo.matches[0]?.away_team}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Cross-match: chaque leg = pari EN PREMIER puis match context */
          combo.matches.map((leg, i) => (
            <div key={i} className="rounded-xl border border-violet-500/25 overflow-hidden">
              {/* Bet — gros, violet, bien visible */}
              <div className="px-4 pt-3.5 pb-3 bg-gradient-to-r from-violet-600/20 to-fuchsia-600/10 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[10px] text-violet-400 font-mono uppercase tracking-widest mb-0.5">
                    ✦ Sélection {i + 1}
                  </div>
                  <div className="text-base font-black text-white leading-snug">{formatMarket(leg.market)}</div>
                </div>
                {leg.odds && (
                  <div className="shrink-0 flex flex-col items-center px-3 py-1.5 rounded-lg bg-yellow-400/15 border border-yellow-400/40">
                    <span className="text-[9px] text-gray-500 font-mono uppercase tracking-wider">Cote</span>
                    <span className="text-lg font-black text-yellow-400 font-mono leading-none">{Number(leg.odds).toFixed(2)}</span>
                  </div>
                )}
              </div>
              {/* Match context */}
              <div className="flex items-center gap-2.5 px-4 py-2 bg-white/3 border-t border-white/5">
                <div className="shrink-0 w-5 h-5 rounded-full bg-violet-500/15 border border-violet-500/25 flex items-center justify-center text-violet-400 text-[10px] font-bold">
                  {i + 1}
                </div>
                <div className="min-w-0">
                  <div className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">{leg.league}</div>
                  <div className="text-xs text-gray-400 truncate">
                    {leg.home_team} <span className="text-gray-600">vs</span> {leg.away_team}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── FOOTER STATS ───────────────────────────────────────── */}
      <div className="px-5 py-3 bg-white/3 border-t border-white/5">
        <div className="grid grid-cols-3 divide-x divide-white/5 text-center text-xs font-mono">
          <div className="px-2">
            <div className="text-gray-500 mb-1 uppercase tracking-wider text-[10px]">Probabilité</div>
            <div className="text-white font-bold text-sm">{(combo.prob * 100).toFixed(1)}%</div>
          </div>
          <div className="px-2">
            <div className="text-gray-500 mb-1 uppercase tracking-wider text-[10px]">Edge</div>
            <div className="text-violet-400 font-bold text-sm">+{combo.edge.toFixed(1)}%</div>
          </div>
          <div className="px-2">
            <div className="text-gray-500 mb-1 uppercase tracking-wider text-[10px]">Kelly</div>
            <div className="text-fuchsia-400 font-bold text-sm">{combo.kelly_stake.toFixed(1)}%</div>
          </div>
        </div>
      </div>
    </div>
  );
}
