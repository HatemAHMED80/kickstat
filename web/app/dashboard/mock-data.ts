// Mock data for testing MatchCard design

export const mockPredictions = [
  {
    match_id: "nice_vs_monaco_2026-02-09",
    league: "Ligue 1",
    home_team: "Nice",
    away_team: "Monaco",
    kickoff: "2026-02-09T20:00:00Z",

    // Model predictions
    model_probs: {
      home: 0.452,
      draw: 0.283,
      away: 0.265
    },

    // Odds
    best_odds: {
      home: 2.60,
      draw: 3.50,
      away: 2.80
    },

    bookmaker: {
      home: "Betclic",
      draw: "Unibet",
      away: "Pinnacle"
    },

    // Edges
    edge: {
      home: 17.4,
      draw: -9.2,
      away: -5.8
    },

    // Quality metrics
    quality_score: 11.7,  // 17.4 × sqrt(0.452) = 11.7
    confidence_badge: "RISKY",  // High edge but <55% prob

    // Over/Under
    over_under: {
      over_25: 0.583,
      under_25: 0.417
    },

    over_under_odds: {
      over_25: 1.92,
      under_25: 2.15
    },

    over_under_edge: {
      over_25: 12.1,
      under_25: -10.3
    },

    // BTTS
    btts: {
      yes: 0.62,
      no: 0.38
    },

    // Correct scores
    correct_score: {
      "1-1": 0.098,
      "2-1": 0.092,
      "1-0": 0.087,
      "0-1": 0.078,
      "2-0": 0.071
    },

    // HOME TEAM STATS
    home_stats: {
      ppg: 1.8,
      goals_scored_avg: 1.6,
      goals_conceded_avg: 0.8,
      shots_per_game: 14.2,
      shots_on_target_per_game: 5.2,
      shot_accuracy: 36.6,
      corners_per_game: 5.8,
      dominance_score: 0.54,
      recent_form: "🟢🟢🔴🟡🟢",
      recent_matches: [
        {
          date: "2026-02-05",
          opponent: "Nantes",
          score: "2-0",
          result: "win" as const,
          home_away: "home",
          clean_sheet: true
        },
        {
          date: "2026-02-01",
          opponent: "Lyon",
          score: "2-1",
          result: "win" as const,
          home_away: "away",
          clean_sheet: false
        },
        {
          date: "2026-01-28",
          opponent: "Marseille",
          score: "0-1",
          result: "loss" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-24",
          opponent: "Lens",
          score: "1-1",
          result: "draw" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-20",
          opponent: "Lille",
          score: "2-0",
          result: "win" as const,
          home_away: "away",
          clean_sheet: true
        }
      ]
    },

    // AWAY TEAM STATS
    away_stats: {
      ppg: 1.4,
      goals_scored_avg: 1.2,
      goals_conceded_avg: 1.4,
      shots_per_game: 11.8,
      shots_on_target_per_game: 4.1,
      shot_accuracy: 34.7,
      corners_per_game: 4.3,
      dominance_score: 0.46,
      recent_form: "🔴🟢🟢🔴🟡",
      recent_matches: [
        {
          date: "2026-02-04",
          opponent: "PSG",
          score: "1-3",
          result: "loss" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-31",
          opponent: "Brest",
          score: "2-0",
          result: "win" as const,
          home_away: "away",
          clean_sheet: true
        },
        {
          date: "2026-01-27",
          opponent: "Reims",
          score: "2-1",
          result: "win" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-23",
          opponent: "Lyon",
          score: "1-3",
          result: "loss" as const,
          home_away: "away",
          clean_sheet: false
        },
        {
          date: "2026-01-19",
          opponent: "Rennes",
          score: "1-1",
          result: "draw" as const,
          home_away: "home",
          clean_sheet: false
        }
      ]
    },

    // HEAD-TO-HEAD
    h2h_stats: {
      total_matches: 10,
      home_wins: 3,
      draws: 4,
      away_wins: 3,
      avg_goals: 2.7,
      over_25_rate: 60,
      recent_results: [
        {
          date: "2025-12-15",
          score: "1-1",
          result: "draw"
        },
        {
          date: "2025-04-28",
          score: "1-2",
          result: "away_win"
        },
        {
          date: "2024-11-18",
          score: "3-2",
          result: "home_win"
        },
        {
          date: "2024-03-10",
          score: "0-0",
          result: "draw"
        },
        {
          date: "2023-09-24",
          score: "2-1",
          result: "home_win"
        }
      ]
    }
  },

  // Second match
  {
    match_id: "psg_vs_marseille_2026-02-09",
    league: "Ligue 1",
    home_team: "Paris SG",
    away_team: "Marseille",
    kickoff: "2026-02-09T20:45:00Z",

    model_probs: {
      home: 0.632,
      draw: 0.241,
      away: 0.127
    },

    best_odds: {
      home: 1.45,
      draw: 4.20,
      away: 7.50
    },

    bookmaker: {
      home: "Pinnacle",
      draw: "Betclic",
      away: "Unibet"
    },

    edge: {
      home: -8.3,
      draw: 1.2,
      away: -4.7
    },

    // Quality metrics
    quality_score: null,  // No qualified bet (edges all < 5% or probs < 35%)
    confidence_badge: null,

    over_under: {
      over_25: 0.721,
      under_25: 0.279
    },

    over_under_odds: {
      over_25: 1.65,
      under_25: 2.40
    },

    over_under_edge: {
      over_25: 19.1,
      under_25: -32.9
    },

    btts: {
      yes: 0.58,
      no: 0.42
    },

    correct_score: {
      "2-1": 0.125,
      "3-1": 0.098,
      "2-0": 0.087,
      "1-0": 0.071,
      "3-0": 0.062
    },

    home_stats: {
      ppg: 2.6,
      goals_scored_avg: 2.8,
      goals_conceded_avg: 0.6,
      shots_per_game: 18.4,
      shots_on_target_per_game: 7.2,
      shot_accuracy: 39.1,
      corners_per_game: 7.2,
      dominance_score: 0.68,
      recent_form: "🟢🟢🟢🟢🟡",
      recent_matches: [
        {
          date: "2026-02-06",
          opponent: "Lyon",
          score: "3-1",
          result: "win" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-02-02",
          opponent: "Lille",
          score: "2-0",
          result: "win" as const,
          home_away: "away",
          clean_sheet: true
        },
        {
          date: "2026-01-29",
          opponent: "Monaco",
          score: "3-1",
          result: "win" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-25",
          opponent: "Nice",
          score: "4-2",
          result: "win" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-21",
          opponent: "Lens",
          score: "2-2",
          result: "draw" as const,
          home_away: "away",
          clean_sheet: false
        }
      ]
    },

    away_stats: {
      ppg: 1.8,
      goals_scored_avg: 1.8,
      goals_conceded_avg: 1.2,
      shots_per_game: 13.6,
      shots_on_target_per_game: 5.4,
      shot_accuracy: 39.7,
      corners_per_game: 5.4,
      dominance_score: 0.52,
      recent_form: "🟢🟡🔴🟢🟢",
      recent_matches: [
        {
          date: "2026-02-05",
          opponent: "Brest",
          score: "3-1",
          result: "win" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-02-01",
          opponent: "Nantes",
          score: "1-1",
          result: "draw" as const,
          home_away: "away",
          clean_sheet: false
        },
        {
          date: "2026-01-28",
          opponent: "Nice",
          score: "1-0",
          result: "win" as const,
          home_away: "away",
          clean_sheet: true
        },
        {
          date: "2026-01-24",
          opponent: "Lyon",
          score: "0-2",
          result: "loss" as const,
          home_away: "home",
          clean_sheet: false
        },
        {
          date: "2026-01-20",
          opponent: "Lille",
          score: "2-1",
          result: "win" as const,
          home_away: "home",
          clean_sheet: false
        }
      ]
    },

    h2h_stats: {
      total_matches: 10,
      home_wins: 6,
      draws: 2,
      away_wins: 2,
      avg_goals: 3.4,
      over_25_rate: 80,
      recent_results: [
        {
          date: "2025-10-27",
          score: "3-0",
          result: "home_win"
        },
        {
          date: "2025-04-14",
          score: "2-2",
          result: "draw"
        },
        {
          date: "2024-11-03",
          score: "4-1",
          result: "home_win"
        },
        {
          date: "2024-03-31",
          score: "1-2",
          result: "away_win"
        },
        {
          date: "2023-09-24",
          score: "4-0",
          result: "home_win"
        }
      ]
    }
  }
];
