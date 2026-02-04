# Data Flow Documentation

## Architecture Overview

Le système utilise **exclusivement des données réelles** provenant de deux APIs:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Football-Data.org (Free Tier)    │    The Odds API (500 req/mois)  │
│  ─────────────────────────────    │    ────────────────────────     │
│  • Fixtures/Matchs                │    • Cotes réelles              │
│  • Equipes                        │    • 25+ bookmakers             │
│  • Classements                    │    • Pinnacle, Bet365, Betfair  │
│  • 5 ligues majeures              │    • PMU, Unibet, 1xBet...      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SYNC SCRIPT (UNIQUE)                              │
│        scripts/sync_football_data.py                                 │
├─────────────────────────────────────────────────────────────────────┤
│  1. Récupère les équipes → stocke en DB                             │
│  2. Récupère les fixtures → stocke en DB                            │
│  3. Récupère les cotes RÉELLES → stocke en DB                       │
│  4. Calcule les prédictions (modèle ELO)                            │
│  5. Compare modèle vs cotes → calcule les edges                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DATABASE                                      │
│                    kickstat.db (SQLite)                             │
├─────────────────────────────────────────────────────────────────────┤
│  • Competition     → Ligues (Ligue 1, PL, La Liga...)               │
│  • Team            → Équipes avec ELO ratings                       │
│  • Match           → Matchs programmés                              │
│  • MatchOdds       → Cotes par bookmaker (RÉELLES)                  │
│  • Prediction      → Probabilités calculées par le modèle          │
│  • EdgeCalculation → Opportunités de value betting                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                                 │
│                    app/api/v1/endpoints/                            │
├─────────────────────────────────────────────────────────────────────┤
│  /api/v1/matches     → Liste des matchs avec prédictions           │
│  /api/v1/predictions → Détails des prédictions                     │
│  /api/v1/odds        → Cotes et calculs d'edges                    │
│  /api/v1/teams       → Équipes et statistiques                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Scripts

### Script Principal: `sync_football_data.py`

C'est le **seul script** à utiliser pour synchroniser les données.

```bash
# Sync Ligue 1 (défaut)
cd backend && python -m scripts.sync_football_data

# Sync une autre ligue
python -m scripts.sync_football_data --league premier_league
python -m scripts.sync_football_data --league la_liga
python -m scripts.sync_football_data --league bundesliga
python -m scripts.sync_football_data --league serie_a

# Sync toutes les ligues
python -m scripts.sync_football_data --league all
```

### Scripts Supprimés (obsolètes)

- ~~`sync_data.py`~~ - Supprimé (générique, confus)
- ~~`sync_real_data.py`~~ - Supprimé (utilisait API-Football avec limites)
- ~~`sync_real_odds.py`~~ - Supprimé (remplacé par sync_football_data)
- ~~`sync_unified.py`~~ - Supprimé (générait des cotes simulées)

## Environment Variables

Variables requises dans `.env` et Render:

```env
# Football-Data.org (gratuit)
FOOTBALL_DATA_ORG_KEY=votre_clé

# The Odds API (500 requêtes/mois gratuites)
ODDS_API_KEY=votre_clé

# Database
DATABASE_URL=sqlite:///./kickstat.db

# Admin
SECRET_KEY=votre_secret
```

## API Clients

### Football-Data.org (`app/services/data/football_data_org.py`)

```python
from app.services.data.football_data_org import get_football_data_client

client = get_football_data_client()
matches = client.get_scheduled_matches("FL1")  # Ligue 1
teams = client.get_teams("PL")  # Premier League
```

Codes des compétitions:
- `FL1` - Ligue 1
- `PL` - Premier League
- `PD` - La Liga
- `BL1` - Bundesliga
- `SA` - Serie A

### The Odds API (`app/services/data/odds_api.py`)

```python
from app.services.data.odds_api import get_odds_api_client

client = get_odds_api_client()
odds = client.get_odds("soccer_france_ligue_one")
```

Sport keys:
- `soccer_france_ligue_one` - Ligue 1
- `soccer_epl` - Premier League
- `soccer_spain_la_liga` - La Liga
- `soccer_germany_bundesliga` - Bundesliga
- `soccer_italy_serie_a` - Serie A

## Auto-Sync au Démarrage

Le backend synchronise automatiquement les données réelles au démarrage si la base est vide:

```python
# app/main.py - lifespan
if team_count == 0:
    from scripts.sync_football_data import sync_fixtures
    sync_fixtures("ligue_1")
```

## Admin Endpoints

### Sync Manuel

```bash
# POST /admin/sync?secret=YOUR_SECRET&league=ligue_1
curl -X POST "https://your-api.render.com/admin/sync?secret=YOUR_SECRET&league=premier_league"
```

## Modèle de Prédiction: Dixon-Coles

### Pourquoi Dixon-Coles ?

Le modèle Dixon-Coles (1997) est supérieur à l'ELO car:
- Modèle de **Poisson** pour les buts (pas juste win/lose)
- Paramètres **attaque/défense** par équipe
- **Correction** pour les scores faibles (0-0, 1-0, 0-1, 1-1)
- Produit des **probabilités de scores exacts**

### Ratings par équipe

Chaque équipe a deux paramètres basés sur les xG:

| Équipe | Attack | Defense |
|--------|--------|---------|
| PSG | 1.638 | 0.572 |
| Monaco | 1.395 | 0.742 |
| OM | 1.331 | 0.866 |
| Lyon | 1.259 | 0.970 |
| Lille | 1.156 | 0.731 |
| ... | ... | ... |
| Défaut | 1.000 | 1.000 |

### Calcul des Expected Goals

```python
# Expected goals par équipe
lambda_home = avg_goals × home_attack × away_defense × (1 + home_advantage)
lambda_away = avg_goals × away_attack × home_defense
```

### Probabilité d'un score exact

```python
# Distribution de Poisson + correction Dixon-Coles
P(h, a) = Poisson(h, λ_home) × Poisson(a, λ_away) × τ(h, a, ρ)
```

### Calcul des Edges

```python
# Edge = (prob_modèle - prob_bookmaker) / prob_bookmaker * 100
edge = (model_prob - book_prob) / book_prob * 100

# Kelly Criterion pour la mise
kelly = (b * p - q) / b  # où b = odds - 1
```

## Fuzzy Team Matching

Les noms d'équipes diffèrent entre les APIs. Le système utilise un matching flou:

```python
def match_teams_fuzzy(name1: str, name2: str) -> bool:
    n1 = name1.lower().replace("fc ", "").replace(" fc", "").strip()
    n2 = name2.lower().replace("fc ", "").replace(" fc", "").strip()
    return n1 in n2 or n2 in n1
```

Exemples:
- "Paris Saint-Germain FC" ↔ "Paris Saint-Germain" ✓
- "Olympique de Marseille" ↔ "Olympique Marseille" ✓

## Troubleshooting

### "No ODDS_API_KEY configured"

Vérifier que `ODDS_API_KEY` est défini dans `.env` et/ou Render.

### Base de données vide après redémarrage

Sur Render (filesystem éphémère), la DB est recréée à chaque déploiement.
Le système re-sync automatiquement au démarrage.

### Pas de cotes pour certains matchs

The Odds API ne couvre que les matchs à venir. Les matchs lointains peuvent ne pas avoir de cotes.

---

## Versions des modèles

| Version | Modèle | Description |
|---------|--------|-------------|
| v1.0-elo | ELO | Legacy - Basé sur ratings ELO simples |
| **v2.0-dixon-coles** | Dixon-Coles | **Actuel** - Modèle de Poisson avec xG |

---

*Dernière mise à jour: Février 2026*
