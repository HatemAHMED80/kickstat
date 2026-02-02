// Shared types for the frontend

export interface Match {
  id: number;
  homeTeam: Team;
  awayTeam: Team;
  kickoff: Date;
  competition: Competition;
  matchday?: number;
  status: "scheduled" | "live" | "finished" | "postponed";
  homeScore?: number;
  awayScore?: number;
  prediction?: Prediction;
}

export interface Team {
  id: number;
  name: string;
  shortName: string;
  code: string;
  logoUrl?: string;
  eloRating: number;
}

export interface Competition {
  id: number;
  name: string;
  shortName: string;
  type: "league" | "cup";
}

export interface Prediction {
  homeWin: number;
  draw: number;
  awayWin: number;
  confidence: number;
  factors?: PredictionFactor[];
}

export interface PredictionFactor {
  name: string;
  impact: string;
  description: string;
}

export interface Standing {
  position: number;
  team: Team;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDifference: number;
  points: number;
  form: string;
}
