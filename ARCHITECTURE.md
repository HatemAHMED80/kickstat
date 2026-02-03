# Architecture Kickstat - Flux de données

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Vercel)                               │
│                         Next.js + React + TypeScript                         │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Landing   │    │  Dashboard  │    │    Login    │    │   Signup    │  │
│  │   Page      │    │    Page     │    │    Page     │    │    Page     │  │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│                            │                   │                   │         │
│                            ▼                   ▼                   ▼         │
│                     ┌─────────────────────────────────────────────────┐     │
│                     │              lib/api.ts (Axios)                 │     │
│                     │         API_BASE_URL = Render backend           │     │
│                     └─────────────────────┬───────────────────────────┘     │
│                                           │                                  │
│                     ┌─────────────────────┴───────────────────────────┐     │
│                     │           lib/supabase.ts (Auth)                │     │
│                     └─────────────────────┬───────────────────────────┘     │
└───────────────────────────────────────────┼─────────────────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────┐
│   BACKEND API (Render)  │  │   SUPABASE (Auth)       │  │  STRIPE (Pmt)   │
│   FastAPI + SQLAlchemy  │  │   PostgreSQL + Auth     │  │  Subscriptions  │
│                         │  │                         │  │                 │
│  kickstat-api.onrender  │  │  qkxglukgwnbjnvmdnosi   │  │  stripe.com     │
│          .com           │  │     .supabase.co        │  │                 │
└───────────┬─────────────┘  └─────────────────────────┘  └─────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BASE DE DONNÉES (SQLite)                            │
│                         data/kickstat.db                                    │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌────────────┐ │
│  │  Teams   │  │  Matches │  │ Predictions│  │ MatchOdds │  │EdgeCalcs   │ │
│  │  (18)    │  │  (18)    │  │   (18)     │  │  (~50)    │  │  (~30)     │ │
│  └──────────┘  └──────────┘  └────────────┘  └───────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Flux de données détaillé

### 1. Dashboard → Opportunités

```
Dashboard (page.tsx)
        │
        │ useEffect() on mount
        ▼
getOpportunities({ min_edge: 5, limit: 20 })
        │
        │ axios.get('/odds/opportunities')
        ▼
┌─────────────────────────────────────────┐
│  GET /api/v1/odds/opportunities         │
│  Backend: odds.py                       │
│                                         │
│  1. EdgeCalculator.get_top_opportunities│
│  2. Query EdgeCalculation table         │
│  3. Join with Match, Team tables        │
│  4. Filter: edge >= min_edge            │
│  5. Filter: Match.status == "scheduled" │
│  6. Filter: Match.kickoff > now()       │
│  7. Order by edge_percentage DESC       │
└─────────────────────────────────────────┘
        │
        │ Response JSON
        ▼
{
  "opportunities": [
    {
      "id": 96,
      "match": {
        "id": 18,
        "home_team": { "name": "Marseille", ... },
        "away_team": { "name": "Toulouse", ... },
        "kickoff": "2026-02-12T21:00:00",
        "competition_name": "Ligue 1"
      },
      "market": "1x2_away",
      "market_display": "Victoire extérieur",
      "model_probability": 0.149,
      "bookmaker_probability": 0.079,
      "edge_percentage": 88.61,
      "best_odds": 12.61,
      "bookmaker_name": "Winamax",
      "risk_level": "safe",
      "confidence": 0.84,
      "kelly_stake": 0.019
    },
    ...
  ],
  "total": 3,
  "free_preview_count": 3
}
        │
        │ setOpportunities(data.opportunities)
        ▼
Dashboard renders OpportunityCard components
```

### 2. Seed Data → Base de données

```
seed_data.py (on startup)
        │
        ▼
┌─────────────────────────────────────────┐
│  1. Create Competition (Ligue 1)        │
│  2. Create 18 Teams with ELO ratings    │
│  3. Create 18 Matches (2 matchdays)     │
│  4. For each match:                     │
│     a. Calculate probabilities (ELO)    │
│     b. Create Prediction                │
│     c. Create MatchOdds (3-4 bookmakers)│
│     d. Calculate edges                  │
│     e. Create EdgeCalculation if >3%    │
└─────────────────────────────────────────┘
```

### 3. Calcul des probabilités (ELO)

```python
# Formule ELO → Probabilité
elo_diff = home_elo - away_elo + 65  # +65 = avantage domicile

home_win_expectancy = 1 / (1 + 10^(-elo_diff / 400))

# Ajustement pour le nul (~26-30% en Ligue 1)
draw_prob = 0.26 + 0.04 * (1 - |home_exp - 0.5| * 2)

home_prob = home_exp * (1 - draw_prob)
away_prob = (1 - home_exp) * (1 - draw_prob)
```

### 4. Calcul de l'edge

```python
# Edge = (Notre probabilité - Probabilité bookmaker) / Probabilité bookmaker * 100

# Exemple:
model_prob = 0.45      # Notre modèle: 45%
odds = 2.50            # Cote bookmaker: 2.50
book_prob = 1/2.50     # = 0.40 (40%)

edge = (0.45 - 0.40) / 0.40 * 100
     = 12.5%           # Avantage de 12.5%
```

## Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v1/odds/opportunities` | GET | Liste des opportunités triées par edge |
| `/api/v1/odds/matches/{id}/edges` | GET | Edges pour un match spécifique |
| `/api/v1/odds/matches/{id}/odds` | GET | Cotes bookmakers pour un match |
| `/api/v1/auth/me` | GET | Info utilisateur connecté |
| `/admin/seed` | POST | Re-seeder la base de données |
| `/health` | GET | Status du serveur |

## Structure des tables

```sql
-- Teams
CREATE TABLE teams (
    id INTEGER PRIMARY KEY,
    name VARCHAR,           -- "Paris Saint-Germain"
    short_name VARCHAR,     -- "PSG"
    elo_rating FLOAT,       -- 1850
    logo_url VARCHAR
);

-- Matches
CREATE TABLE matches (
    id INTEGER PRIMARY KEY,
    home_team_id INTEGER,
    away_team_id INTEGER,
    competition_id INTEGER,
    kickoff DATETIME,
    matchday INTEGER,
    status VARCHAR          -- "scheduled", "live", "finished"
);

-- Predictions (notre modèle)
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY,
    match_id INTEGER,
    home_win_prob FLOAT,    -- 62.0 (en %)
    draw_prob FLOAT,        -- 24.0
    away_win_prob FLOAT,    -- 14.0
    confidence FLOAT,       -- 0.85
    model_version VARCHAR   -- "v1.0-elo"
);

-- MatchOdds (bookmakers)
CREATE TABLE match_odds (
    id INTEGER PRIMARY KEY,
    match_id INTEGER,
    bookmaker VARCHAR,      -- "Betclic"
    home_win_odds FLOAT,    -- 1.61
    draw_odds FLOAT,        -- 4.00
    away_win_odds FLOAT     -- 5.50
);

-- EdgeCalculations (opportunités)
CREATE TABLE edge_calculations (
    id INTEGER PRIMARY KEY,
    match_id INTEGER,
    market VARCHAR,         -- "1x2_home", "over_25", etc.
    model_probability FLOAT,
    bookmaker_probability FLOAT,
    edge_percentage FLOAT,  -- 12.5
    best_odds FLOAT,
    bookmaker_name VARCHAR,
    risk_level VARCHAR,     -- "safe", "medium", "risky"
    kelly_stake FLOAT
);
```

## Variables d'environnement

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=https://kickstat-api.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

### Backend (Render)
```
DATABASE_URL=sqlite:///./data/kickstat.db
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=xxx
```
