'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import MatchCard from '../components/MatchCard';
import { mockPredictions } from './mock-data';

// Type definitions
interface Prediction {
  match_id: string;
  league: string;
  home_team: string;
  away_team: string;
  kickoff: string;
  model_probs: { home: number; draw: number; away: number };
  best_odds: { home: number; draw: number; away: number };
  bookmaker: { home: string; draw: string; away: string };
  edge: { home: number; draw: number; away: number };
  recommended_bet: string | null;
  kelly_stake: number;
  segment: string;
  over_under_15?: { over_15: number; under_15: number } | null;
  over_under_15_odds?: { over_15: number; under_15: number } | null;
  over_under_15_edge?: { over_15: number; under_15: number } | null;
  over_under?: { over_25: number; under_25: number } | null;
  over_under_odds?: { over_25: number; under_25: number } | null;
  over_under_edge?: { over_25: number; under_25: number } | null;
  over_under_35?: { over_35: number; under_35: number } | null;
  over_under_35_odds?: { over_35: number; under_35: number } | null;
  over_under_35_edge?: { over_35: number; under_35: number } | null;
  btts?: { yes: number; no: number } | null;
  btts_odds?: { yes: number; no: number } | null;
  btts_edge?: { yes: number; no: number } | null;
  correct_score?: { [key: string]: number } | null;
}

// No mock data - we want to see real errors if API fails

export default function Dashboard() {
  const [selectedLeague, setSelectedLeague] = useState<string>('all');
  const [minEdge, setMinEdge] = useState<number>(3);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Use mock data for design testing
  useEffect(() => {
    setLoading(true);

    // Simulate API delay
    setTimeout(() => {
      // @ts-ignore - Using mock data
      setPredictions(mockPredictions);
      setLoading(false);
      setError(null);
    }, 500);
  }, [selectedLeague, minEdge]);

  const filteredPredictions = predictions.filter(pred => {
    if (selectedLeague !== 'all' && pred.league !== selectedLeague) return false;
    const maxEdge = Math.max(pred.edge.home, pred.edge.draw, pred.edge.away);
    if (maxEdge < minEdge) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-black">
      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gradient-to-r from-gray-900 via-black to-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link href="/" className="flex items-center group">
              <span className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent group-hover:from-emerald-400 group-hover:to-cyan-400 transition">
                ⚽ SmartBet Pro
              </span>
            </Link>
            <div className="flex items-center space-x-4">
              <Link href="/dashboard" className="text-cyan-400 font-semibold hover:text-emerald-400 transition">Dashboard</Link>
              <Link href="/#pricing" className="text-gray-400 hover:text-cyan-400 transition">Upgrade</Link>
              <button className="px-4 py-2 rounded-lg border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 hover:border-cyan-500/50 transition">
                Login
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Header */}
      <div className="bg-gradient-to-r from-gray-900 via-black to-gray-900 border-b border-cyan-500/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white">Live Predictions</h1>
            <span className="px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold uppercase tracking-wide animate-pulse">
              Real-time
            </span>
          </div>
          <p className="text-gray-400 font-mono text-sm">
            {new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-gray-900/50 border-b border-gray-800/50 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div>
              <label className="text-xs font-mono uppercase tracking-wider text-gray-500 mr-2">League:</label>
              <select
                value={selectedLeague}
                onChange={(e) => setSelectedLeague(e.target.value)}
                className="px-4 py-2 bg-gray-800/50 border border-gray-700/50 text-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 hover:border-cyan-500/30 transition font-mono"
              >
                <option value="all">All Leagues</option>
                <option value="Ligue 1">Ligue 1</option>
                <option value="Premier League">Premier League</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-mono uppercase tracking-wider text-gray-500 mr-2">Min Edge:</label>
              <select
                value={minEdge}
                onChange={(e) => setMinEdge(Number(e.target.value))}
                className="px-4 py-2 bg-gray-800/50 border border-gray-700/50 text-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 hover:border-cyan-500/30 transition font-mono"
              >
                <option value="0">0%+</option>
                <option value="3">3%+</option>
                <option value="5">5%+ (Recommended)</option>
                <option value="8">8%+ (High Value)</option>
              </select>
            </div>

            <div className="ml-auto flex items-center gap-3">
              <span className="text-sm text-gray-500 font-mono">
                <span className="text-cyan-400 font-bold">{filteredPredictions.length}</span> predictions
              </span>
              <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Predictions Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-4 border-cyan-500/30 border-t-cyan-500 mb-4"></div>
            <p className="text-gray-300 font-semibold">Analyzing matches...</p>
            <p className="text-gray-500 text-sm mt-2 font-mono">Calibrating Dixon-Coles + ELO models</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-red-900/20 border-2 border-red-500/50 rounded-lg p-6 mb-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 text-4xl">❌</div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-red-400 mb-2">Connection Error</h3>
                <p className="text-red-300 text-sm mb-3">{error}</p>
                <div className="bg-black/50 rounded border border-red-500/30 p-3 text-xs font-mono text-gray-400">
                  <div className="font-bold text-red-400 mb-1">Quick fix:</div>
                  <code className="block text-cyan-400">cd /Users/hatemahmed/football-predictions</code>
                  <code className="block text-cyan-400">uvicorn api.main:app --port 8002 --reload</code>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Predictions */}
        {!loading && (
          <>
            <div className="grid gap-6">
              {filteredPredictions.map((pred) => (
                <MatchCard key={pred.match_id} prediction={pred} />
              ))}
            </div>

            {filteredPredictions.length === 0 && (
              <div className="text-center py-12">
                <div className="text-gray-600 text-5xl mb-4">📭</div>
                <p className="text-gray-400 text-lg font-semibold">No predictions match your filters</p>
                <p className="text-gray-600 text-sm mt-2 font-mono">Try lowering the edge threshold</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Upgrade CTA */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-16">
        <div className="relative bg-gradient-to-r from-gray-900 via-black to-gray-900 rounded-2xl p-8 text-center border border-cyan-500/30 overflow-hidden">
          {/* Glow effect */}
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-emerald-500/10 to-cyan-500/10 blur-xl"></div>

          <div className="relative z-10">
            <h3 className="text-2xl font-bold text-transparent bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text mb-4">
              Unlock Pro Features 🚀
            </h3>
            <p className="text-gray-400 mb-6 font-mono text-sm">
              Real-time SMS alerts • Advanced analytics • Kelly calculator • Priority support
            </p>
            <Link
              href="/#pricing"
              className="inline-block px-8 py-3 bg-gradient-to-r from-cyan-500 to-emerald-500 text-black font-bold rounded-lg hover:from-emerald-500 hover:to-cyan-500 transition shadow-lg shadow-cyan-500/20"
            >
              View Pricing →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

interface PredictionCardProps {
  prediction: Prediction;
}

function PredictionCard({ prediction }: PredictionCardProps) {
  const getBetType = () => {
    const maxEdge = Math.max(prediction.edge.home, prediction.edge.draw, prediction.edge.away);
    if (prediction.edge.home === maxEdge) return 'home';
    if (prediction.edge.away === maxEdge) return 'away';
    return 'draw';
  };

  const betType = getBetType();
  const betProb = prediction.model_probs[betType as keyof typeof prediction.model_probs];
  const betEdge = prediction.edge[betType as keyof typeof prediction.edge];
  const betOdds = prediction.best_odds[betType as keyof typeof prediction.best_odds];
  const betBookmaker = prediction.bookmaker[betType as keyof typeof prediction.bookmaker];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition">
      {/* Header */}
      <div className="p-6 border-b bg-gray-50">
        <div className="flex justify-between items-start mb-4">
          <div>
            <span className="inline-block px-3 py-1 bg-blue-100 text-blue-700 text-sm font-medium rounded-full mb-2">
              {prediction.league}
            </span>
            <h3 className="text-xl font-bold text-gray-900">
              {prediction.home_team} vs {prediction.away_team}
            </h3>
            <p className="text-sm text-gray-600 mt-1">
              {new Date(prediction.kickoff).toLocaleString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              })}
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-600 mb-1">Segment</div>
            <div className="text-sm font-medium text-gray-900">{prediction.segment}</div>
          </div>
        </div>
      </div>

      {/* Recommendation Banner */}
      <div className="px-6 py-4 bg-gradient-to-r from-green-50 to-emerald-50 border-b border-green-100">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center text-white font-bold text-xl">
              ✓
            </div>
            <div>
              <div className="text-sm text-green-700 font-medium">RECOMMENDED BET</div>
              <div className="text-lg font-bold text-green-900">
                {betType === 'home' && prediction.home_team}
                {betType === 'away' && prediction.away_team}
                {betType === 'draw' && 'Draw'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-green-900">{betOdds.toFixed(2)}</div>
            <div className="text-xs text-green-700">@ {betBookmaker}</div>
          </div>
        </div>

        {/* Why This Bet - Explanation */}
        <div className="bg-white/60 rounded-lg p-3 mb-3 border border-green-200">
          <div className="flex items-start gap-2">
            <div className="text-lg">💡</div>
            <div className="flex-1">
              <div className="text-xs font-semibold text-green-800 mb-1">Why this bet?</div>
              <div className="text-xs text-green-900">
                {(() => {
                  const marketProb = (1 / betOdds) * 100;
                  const modelProb = betProb * 100;
                  const diff = modelProb - marketProb;
                  return (
                    <>
                      Market undervalues this outcome at <span className="font-bold">{marketProb.toFixed(1)}%</span> (odds {betOdds.toFixed(2)}),
                      but our AI model predicts <span className="font-bold">{modelProb.toFixed(1)}%</span> —
                      a <span className="font-bold text-green-700">+{diff.toFixed(1)}pp edge</span> opportunity.
                    </>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>

        {/* Risk Level */}
        <div className="flex items-center gap-3 mb-3">
          <div className="text-xs text-green-700 font-medium">Risk Level:</div>
          {(() => {
            const probPercent = betProb * 100;
            let riskLevel, riskColor, riskBg, riskIcon;

            if (probPercent >= 60) {
              riskLevel = 'LOW';
              riskColor = 'text-blue-700';
              riskBg = 'bg-blue-100 border-blue-300';
              riskIcon = '🛡️';
            } else if (probPercent >= 40) {
              riskLevel = 'MEDIUM';
              riskColor = 'text-yellow-700';
              riskBg = 'bg-yellow-100 border-yellow-300';
              riskIcon = '⚖️';
            } else {
              riskLevel = 'HIGH';
              riskColor = 'text-red-700';
              riskBg = 'bg-red-100 border-red-300';
              riskIcon = '⚠️';
            }

            return (
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border ${riskBg}`}>
                <span>{riskIcon}</span>
                <span className={`text-xs font-bold ${riskColor}`}>{riskLevel} RISK</span>
                <span className="text-xs text-gray-600">({probPercent.toFixed(1)}% win probability)</span>
              </div>
            );
          })()}
        </div>

        {/* Stats with Explanations */}
        <div className="space-y-2">
          <div className="flex gap-4">
            <div>
              <span className="text-xs text-green-700">Model Probability</span>
              <div className="text-sm font-bold text-green-900">{(betProb * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="text-xs text-green-700">Edge</span>
                <span className="text-xs text-green-600" title="Edge explanation">ℹ️</span>
              </div>
              <div className="text-sm font-bold text-green-900">+{betEdge.toFixed(1)}%</div>
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="text-xs text-green-700">Kelly Stake</span>
                <span className="text-xs text-green-600" title="Kelly explanation">ℹ️</span>
              </div>
              <div className="text-sm font-bold text-green-900">{prediction.kelly_stake.toFixed(1)}% bankroll</div>
            </div>
          </div>

          {/* Explanations */}
          <div className="text-xs text-green-800 space-y-1 bg-white/40 rounded p-2 border border-green-200">
            <div className="flex gap-2">
              <span className="font-semibold min-w-[60px]">📊 Edge:</span>
              <span>How much better our model is vs the market. Higher = more profitable long-term.</span>
            </div>
            <div className="flex gap-2">
              <span className="font-semibold min-w-[60px]">💰 Kelly:</span>
              <span>Optimal bet size to maximize growth while managing risk (25% of full Kelly for safety).</span>
            </div>
          </div>
        </div>
      </div>

      {/* Odds Comparison */}
      <div className="p-6">
        <h4 className="font-semibold text-gray-900 mb-4">Odds Comparison</h4>
        <div className="grid grid-cols-3 gap-4">
          <OddsBox
            label={prediction.home_team}
            modelProb={prediction.model_probs.home}
            odds={prediction.best_odds.home}
            bookmaker={prediction.bookmaker.home}
            edge={prediction.edge.home}
            isRecommended={betType === 'home'}
          />
          <OddsBox
            label="Draw"
            modelProb={prediction.model_probs.draw}
            odds={prediction.best_odds.draw}
            bookmaker={prediction.bookmaker.draw}
            edge={prediction.edge.draw}
            isRecommended={betType === 'draw'}
          />
          <OddsBox
            label={prediction.away_team}
            modelProb={prediction.model_probs.away}
            odds={prediction.best_odds.away}
            bookmaker={prediction.bookmaker.away}
            edge={prediction.edge.away}
            isRecommended={betType === 'away'}
          />
        </div>
      </div>

      {/* Additional Markets: Over/Under, BTTS & Correct Score */}
      {(prediction.over_under_15 || prediction.over_under || prediction.over_under_35 || prediction.btts || prediction.correct_score) && (
        <div className="px-6 py-4 border-t bg-gray-50">
          <h4 className="font-semibold text-gray-900 mb-4">Other Markets</h4>

          {/* Over/Under Goals */}
          <div className="mb-6">
            <div className="text-sm font-semibold text-gray-700 mb-3">⚽ Over/Under Goals</div>

            {/* Over/Under 1.5 */}
            {prediction.over_under_15 && (
              <div className="mb-4">
                <div className="text-xs text-gray-500 mb-2 font-medium">1.5 Goals</div>
                {prediction.over_under_15_odds && prediction.over_under_15_odds.over_15 > 0 ? (
                  <div className="grid grid-cols-2 gap-4">
                    <OddsBox
                      label="Over 1.5"
                      modelProb={prediction.over_under_15.over_15}
                      odds={prediction.over_under_15_odds.over_15}
                      bookmaker="Best odds"
                      edge={prediction.over_under_15_edge?.over_15 || 0}
                      isRecommended={false}
                    />
                    <OddsBox
                      label="Under 1.5"
                      modelProb={prediction.over_under_15.under_15}
                      odds={prediction.over_under_15_odds.under_15}
                      bookmaker="Best odds"
                      edge={prediction.over_under_15_edge?.under_15 || 0}
                      isRecommended={false}
                    />
                  </div>
                ) : (
                  <div className="bg-white rounded-lg border-2 border-gray-200 p-4">
                    <div className="text-center text-gray-500 text-sm">
                      <div className="mb-2">📊 Model predictions available:</div>
                      <div className="flex justify-around mb-3">
                        <div><span className="font-semibold">Over:</span> {(prediction.over_under_15.over_15 * 100).toFixed(1)}%</div>
                        <div><span className="font-semibold">Under:</span> {(prediction.over_under_15.under_15 * 100).toFixed(1)}%</div>
                      </div>
                      <div className="text-xs text-orange-600 bg-orange-50 rounded px-3 py-2 border border-orange-200">
                        ⚠️ Odds not available yet from bookmakers
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Over/Under 2.5 */}
            {prediction.over_under && (
              <div className="mb-4">
                <div className="text-xs text-gray-500 mb-2 font-medium">2.5 Goals</div>
                <div className="grid grid-cols-2 gap-4">
                  <OddsBox
                    label="Over 2.5"
                    modelProb={prediction.over_under.over_25}
                    odds={prediction.over_under_odds?.over_25 || 0}
                    bookmaker={prediction.over_under_odds ? "Best odds" : "N/A"}
                    edge={prediction.over_under_edge?.over_25 || 0}
                    isRecommended={false}
                  />
                  <OddsBox
                    label="Under 2.5"
                    modelProb={prediction.over_under.under_25}
                    odds={prediction.over_under_odds?.under_25 || 0}
                    bookmaker={prediction.over_under_odds ? "Best odds" : "N/A"}
                    edge={prediction.over_under_edge?.under_25 || 0}
                    isRecommended={false}
                  />
                </div>
              </div>
            )}

            {/* Over/Under 3.5 */}
            {prediction.over_under_35 && (
              <div className="mb-4">
                <div className="text-xs text-gray-500 mb-2 font-medium">3.5 Goals</div>
                {prediction.over_under_35_odds && prediction.over_under_35_odds.over_35 > 0 ? (
                  <div className="grid grid-cols-2 gap-4">
                    <OddsBox
                      label="Over 3.5"
                      modelProb={prediction.over_under_35.over_35}
                      odds={prediction.over_under_35_odds.over_35}
                      bookmaker="Best odds"
                      edge={prediction.over_under_35_edge?.over_35 || 0}
                      isRecommended={false}
                    />
                    <OddsBox
                      label="Under 3.5"
                      modelProb={prediction.over_under_35.under_35}
                      odds={prediction.over_under_35_odds.under_35}
                      bookmaker="Best odds"
                      edge={prediction.over_under_35_edge?.under_35 || 0}
                      isRecommended={false}
                    />
                  </div>
                ) : (
                  <div className="bg-white rounded-lg border-2 border-gray-200 p-4">
                    <div className="text-center text-gray-500 text-sm">
                      <div className="mb-2">📊 Model predictions available:</div>
                      <div className="flex justify-around mb-3">
                        <div><span className="font-semibold">Over:</span> {(prediction.over_under_35.over_35 * 100).toFixed(1)}%</div>
                        <div><span className="font-semibold">Under:</span> {(prediction.over_under_35.under_35 * 100).toFixed(1)}%</div>
                      </div>
                      <div className="text-xs text-orange-600 bg-orange-50 rounded px-3 py-2 border border-orange-200">
                        ⚠️ Odds not available yet from bookmakers
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* BTTS */}
          {prediction.btts && (
            <div className="mb-6">
              <div className="text-sm font-semibold text-gray-700 mb-3">🎯 Both Teams To Score</div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-lg border-2 border-gray-200 p-4">
                  <div className="text-xs text-gray-600 mb-1">Yes</div>
                  <div className="text-2xl font-bold text-gray-900">{(prediction.btts.yes * 100).toFixed(1)}%</div>
                  <div className="text-xs text-gray-600 mt-2">Model probability</div>
                </div>
                <div className="bg-white rounded-lg border-2 border-gray-200 p-4">
                  <div className="text-xs text-gray-600 mb-1">No</div>
                  <div className="text-2xl font-bold text-gray-900">{(prediction.btts.no * 100).toFixed(1)}%</div>
                  <div className="text-xs text-gray-600 mt-2">Model probability</div>
                </div>
              </div>
            </div>
          )}

          {/* Correct Score */}
          {prediction.correct_score && (
            <div>
              <div className="text-sm font-semibold text-gray-700 mb-3">🎲 Most Likely Scores</div>
              <div className="bg-white rounded-lg border-2 border-gray-200 p-4">
                <div className="grid grid-cols-5 gap-3">
                  {Object.entries(prediction.correct_score).slice(0, 5).map(([score, prob], idx) => (
                    <div key={score} className="text-center">
                      <div className="text-xs text-gray-500 mb-1">#{idx + 1}</div>
                      <div className="text-xl font-bold text-gray-900">{score}</div>
                      <div className="text-xs text-gray-600 mt-1">{(prob * 100).toFixed(1)}%</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Button */}
      <div className="px-6 pb-6">
        <a
          href={`https://betclic.fr`}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full py-3 bg-blue-600 text-white text-center font-semibold rounded-lg hover:bg-blue-700 transition"
        >
          Bet on {betBookmaker} →
        </a>
        <p className="text-xs text-gray-500 text-center mt-2">
          Affiliate link - We earn commission if you sign up
        </p>
      </div>
    </div>
  );
}

interface OddsBoxProps {
  label: string;
  modelProb: number;
  odds: number;
  bookmaker: string;
  edge: number;
  isRecommended: boolean;
}

function OddsBox({ label, modelProb, odds, bookmaker, edge, isRecommended }: OddsBoxProps) {
  return (
    <div className={`p-4 rounded-lg border-2 ${
      isRecommended
        ? 'border-green-500 bg-green-50'
        : edge > 0
        ? 'border-blue-200 bg-blue-50'
        : 'border-gray-200 bg-gray-50'
    }`}>
      <div className="text-xs text-gray-600 mb-1 truncate">{label}</div>
      <div className="text-2xl font-bold text-gray-900">{odds.toFixed(2)}</div>
      <div className="text-xs text-gray-600 mb-2">@ {bookmaker}</div>
      <div className="text-xs">
        <span className="text-gray-600">Model: </span>
        <span className="font-medium">{(modelProb * 100).toFixed(1)}%</span>
      </div>
      <div className="text-xs">
        <span className="text-gray-600">Edge: </span>
        <span className={`font-medium ${edge > 0 ? 'text-green-600' : 'text-gray-400'}`}>
          {edge > 0 ? '+' : ''}{edge.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}
