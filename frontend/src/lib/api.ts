import axios from "axios";
import { getSupabase } from "./supabase";

// Use Render API in production, localhost in development
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production"
    ? "https://kickstat-api.onrender.com"
    : "http://localhost:8000");

console.log("[API] NODE_ENV:", process.env.NODE_ENV);
console.log("[API] NEXT_PUBLIC_API_URL:", process.env.NEXT_PUBLIC_API_URL);
console.log("[API] Using API_BASE_URL:", API_BASE_URL);

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests automatically
api.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    const supabase = getSupabase();
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  }
  return config;
});

// API response types
export interface Match {
  id: number;
  home_team: Team;
  away_team: Team;
  kickoff: string;
  competition: string;
  matchday?: number;
  prediction?: Prediction;
}

export interface Team {
  id: number;
  name: string;
  short_name: string;
  logo_url?: string;
  elo_rating?: number;
}

export interface Prediction {
  home_win: number;
  draw: number;
  away_win: number;
  confidence: number;
}

// API functions
export async function getUpcomingMatches(limit = 10): Promise<Match[]> {
  const response = await api.get("/matches/upcoming", { params: { limit } });
  return response.data.matches;
}

export async function getMatchPrediction(matchId: number) {
  const response = await api.get(`/matches/${matchId}/prediction`);
  return response.data;
}

export async function getTeam(teamId: number): Promise<Team> {
  const response = await api.get(`/teams/${teamId}`);
  return response.data;
}

export async function getStandings(competitionId: number) {
  const response = await api.get(`/competitions/${competitionId}/standings`);
  return response.data;
}

// =============================================================================
// Kickstat Web App API Functions
// =============================================================================

// Edge/Opportunity types (matching backend response)
export interface TeamInfo {
  id: number;
  name: string;
  short_name: string | null;
  logo_url: string | null;
}

export interface MatchInfo {
  id: number;
  home_team: TeamInfo;
  away_team: TeamInfo;
  kickoff: string;
  competition_name: string | null;
  matchday: number | null;
}

export interface OpportunityResponse {
  id: number;
  match: MatchInfo;
  market: string;
  market_display: string;
  model_probability: number;
  bookmaker_probability: number;
  edge_percentage: number;
  best_odds: number;
  bookmaker_name: string;
  risk_level: "safe" | "medium" | "risky";
  confidence: number;
  kelly_stake: number | null;
}

export interface OpportunitiesListResponse {
  opportunities: OpportunityResponse[];
  total: number;
  free_preview_count: number;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string | null;
  subscription_tier: string;
  subscription_status: string;
  telegram_connected: boolean;
  telegram_alerts_enabled: boolean;
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  price_eur: number;
  interval: string;
  features: string[];
}

export interface PlansResponse {
  plans: SubscriptionPlan[];
  match_price_cents: number;
}

// Auth
export async function getCurrentUser(): Promise<UserResponse> {
  const response = await api.get("/auth/me");
  return response.data;
}

export async function generateTelegramToken() {
  const response = await api.post("/auth/telegram/connect");
  return response.data;
}

export async function disconnectTelegram() {
  const response = await api.delete("/auth/telegram");
  return response.data;
}

// Opportunities
export async function getOpportunities(params?: {
  min_edge?: number;
  risk_level?: string;
  competition_id?: number;
  limit?: number;
}): Promise<OpportunitiesListResponse> {
  const response = await api.get("/odds/opportunities", { params });
  return response.data;
}

export async function getMatchDetails(matchId: number) {
  const response = await api.get(`/odds/matches/${matchId}`);
  return response.data;
}

// Subscriptions
export async function getSubscriptionPlans(): Promise<PlansResponse> {
  const response = await api.get("/subscriptions/plans");
  return response.data;
}

export async function createCheckoutSession(plan: "basic" | "pro") {
  const response = await api.post("/subscriptions/checkout", { plan });
  return response.data;
}

export async function createMatchPurchase(matchId: number) {
  const response = await api.post("/subscriptions/purchase-match", {
    match_id: matchId,
  });
  return response.data;
}

export async function getSubscriptionStatus() {
  const response = await api.get("/subscriptions/status");
  return response.data;
}

export async function getCustomerPortalUrl() {
  const response = await api.get("/subscriptions/portal");
  return response.data;
}

// =============================================================================
// Match Analysis (Dixon-Coles) Types
// =============================================================================

export interface MatchAnalysisTeam {
  id: number;
  name: string;
  short_name: string | null;
  logo_url: string | null;
}

export interface MatchAnalysisInfo {
  id: number;
  home_team: MatchAnalysisTeam;
  away_team: MatchAnalysisTeam;
  kickoff: string;
  competition: string;
  matchday: number | null;
}

export interface ExactScore {
  score: string;
  probability: number;
}

export interface EdgeInfo {
  market: string;
  market_display: string;
  model_probability: number;
  bookmaker_probability: number;
  edge_percentage: number;
  best_odds: number;
  risk_level: string;
  kelly_stake: number;
  confidence: number;
}

export interface Recommendation {
  market: string;
  market_display: string;
  edge: number;
  odds: number;
  stake: string;
  risk: string;
}

export interface MatchAnalysisResponse {
  match: MatchAnalysisInfo;
  has_access: boolean;
  analysis?: {
    expected_goals: {
      home: number;
      away: number;
      total: number;
    };
    probabilities: {
      "1x2": {
        home_win: number;
        draw: number;
        away_win: number;
      };
      over_under: {
        "over_1.5": number;
        "under_1.5": number;
        "over_2.5": number;
        "under_2.5": number;
        "over_3.5": number;
        "under_3.5": number;
      };
      btts: {
        btts_yes: number;
        btts_no: number;
      };
    };
    exact_scores: ExactScore[];
    asian_handicaps: Record<string, number>;
    score_matrix: number[][];
    // Extended markets (at same level as probabilities)
    double_chance?: {
      "1x": number;
      "x2": number;
      "12": number;
    };
    draw_no_bet?: {
      home: number;
      away: number;
    };
    clean_sheet?: {
      home: number;
      away: number;
    };
    win_to_nil?: {
      home: number;
      away: number;
    };
    team_scores?: {
      home: number;
      away: number;
    };
    exact_totals?: Record<string, number>;
    odd_even?: {
      odd: number;
      even: number;
    };
    margin_home?: {
      by_1: number;
      by_2: number;
      by_3_plus: number;
    };
    home_exact_goals?: Record<string, number>;
    away_exact_goals?: Record<string, number>;
    team_overs?: {
      home_o05: number;
      home_o15: number;
      away_o05: number;
      away_o15: number;
    };
  };
  edges?: EdgeInfo[];
  odds?: {
    bookmaker: string;
    home_win: number | null;
    draw: number | null;
    away_win: number | null;
    over_25: number | null;
    under_25: number | null;
    btts_yes: number | null;
    btts_no: number | null;
  };
  recommendations?: Recommendation[];
  preview?: {
    best_edge: number;
    edges_count: number;
    expected_goals_total: number;
  };
  message?: string;
}

// Get full match analysis (Dixon-Coles)
export async function getMatchAnalysis(matchId: number): Promise<MatchAnalysisResponse> {
  const response = await api.get(`/odds/matches/${matchId}/analysis`);
  return response.data;
}
