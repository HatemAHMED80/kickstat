# Setup du projet KickStat

## 1. Cloner le repo

```bash
git clone https://github.com/HatemAHMED80/kickstat.git
cd kickstat
```

## 2. Configurer les clés API

Crée un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
```

Puis colle les clés API que Papa t'a envoyées par message :

```
FOOTBALL_DATA_ORG_KEY=xxx
ODDS_API_KEY=xxx
API_FOOTBALL_KEY=xxx
```

## 3. Setup Python (backend + ML)

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate    # Mac/Linux

# Installer les dépendances
pip install -e .

# Installer aussi les deps de l'API
pip install -r api/requirements.txt
```

## 4. Setup Node (dashboard web)

```bash
cd web
npm install
cd ..
```

## 5. Vérifier que tout marche

### Lancer l'API
```bash
source venv/bin/activate
cd api
uvicorn main:app --reload --port 8000
```
L'API tourne sur http://localhost:8000 - teste avec http://localhost:8000/health

### Lancer le dashboard
```bash
cd web
npm run dev
```
Le dashboard tourne sur http://localhost:3000

### Lancer les notebooks
```bash
source venv/bin/activate
jupyter notebook
```

## Structure du projet

```
kickstat/
├── src/                  # Code source Python
│   ├── models/           # Modèles ML (Dixon-Coles, XGBoost, Ensemble)
│   ├── data/             # Sources de données (APIs, scraping)
│   └── evaluation/       # Backtest, calibration
├── api/                  # API FastAPI (backend)
├── web/                  # Dashboard Next.js + Tailwind
├── scripts/              # Scripts utilitaires (backtest, odds, etc.)
├── notebooks/            # Notebooks Jupyter (exploration, fitting)
├── data/
│   ├── historical/       # CSVs de matchs historiques (dans git)
│   ├── results/          # Résultats de backtest (dans git)
│   └── raw/              # Données brutes (PAS dans git, se téléchargent)
└── .env                  # Clés API (PAS dans git, à créer manuellement)
```

## Créer ta branche de travail

```bash
git checkout -b feature/ton-nom-de-feature
# ... fais tes modifs ...
git add .
git commit -m "description de tes changements"
git push -u origin feature/ton-nom-de-feature
```
