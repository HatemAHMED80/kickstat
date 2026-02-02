# Football Prediction System

Système de prédiction de matchs de football pour la Ligue 1 et les coupes françaises.

## Stack Technique

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, XGBoost
- **Frontend**: Next.js 14, React, TailwindCSS
- **Database**: PostgreSQL, Redis
- **ML**: scikit-learn, XGBoost, MLflow

## Structure du Projet

```
football-predictions/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Endpoints API
│   │   ├── core/            # Configuration
│   │   ├── models/          # Modèles SQLAlchemy
│   │   ├── schemas/         # Schémas Pydantic
│   │   └── services/        # Logique métier
│   │       ├── scrapers/    # Collecte données
│   │       ├── ml/          # Modèles ML
│   │       └── data/        # Traitement données
│   ├── tests/
│   ├── scripts/
│   └── migrations/
├── frontend/
│   └── src/
│       ├── app/             # Pages Next.js
│       ├── components/      # Composants React
│       ├── lib/             # Utilitaires
│       └── types/           # Types TypeScript
├── data/
│   ├── raw/                 # Données brutes
│   └── processed/           # Données traitées
└── notebooks/               # Jupyter notebooks
```

## Installation

### Prérequis

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copier et configurer les variables d'environnement
cp ../.env.example .env

# Lancer le serveur
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | /api/v1/matches/upcoming | Prochains matchs avec prédictions |
| GET | /api/v1/matches/{id}/prediction | Prédiction détaillée |
| GET | /api/v1/teams/{id}/stats | Stats équipe |
| GET | /api/v1/competitions/{id}/standings | Classement |

## Roadmap

- [x] Phase 0: Setup infrastructure
- [ ] Phase 1A: Data Collection (API-Football, Transfermarkt)
- [ ] Phase 1B: Feature Engineering (ELO, forme récente)
- [ ] Phase 1C: Premier modèle ML
- [ ] Phase 2: Enrichissement (xG, météo, arbitres)
- [ ] Phase 3: NLP (analyse presse)

## License

Projet privé - Usage personnel uniquement.
