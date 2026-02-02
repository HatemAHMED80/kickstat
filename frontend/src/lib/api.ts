import axios from "axios";
import { getSupabase } from "./supabase";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

// Edge/Opportunity types
export interface Edge {
  id: number;
  match_id: number;
  market: string;
  model_probability: number;
  bookmaker_probability: number;
  edge_percentage: number;
  best_odds: number;
  bookmaker_name: string;
  risk_level: string;
  kelly_stake: number;
  confidence: number;
}

export interface Opportunity {
  match: Match;
  prediction: Prediction;
  edges: Edge[];
  best_edge: Edge;
}

// Auth
export async function getCurrentUser() {
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
}) {
  const response = await api.get("/odds/opportunities", { params });
  return response.data;
}

export async function getMatchDetails(matchId: number) {
  const response = await api.get(`/odds/matches/${matchId}`);
  return response.data;
}

// Subscriptions
export async function getSubscriptionPlans() {
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
