# Guide d'installation Kickstat

Ce guide détaille toutes les étapes pour configurer et lancer le projet Kickstat.

---

## Prérequis

- **Python** 3.11+
- **Node.js** 18+
- **PostgreSQL** 15+ (ou Docker)
- **Redis** 7+ (ou Docker)

---

## Étape 1 : Services externes

### 1.1 Créer un projet Supabase

1. Va sur https://supabase.com et crée un compte
2. Clique **"New Project"**
3. Choisis un nom (ex: `kickstat`) et un mot de passe DB
4. Attends que le projet soit créé (~2 min)
5. Va dans **Settings → API** et note :
   - `Project URL` → SUPABASE_URL
   - `anon public` → SUPABASE_ANON_KEY
   - `service_role` → SUPABASE_SERVICE_ROLE_KEY
6. Va dans **Settings → API → JWT Settings** et note :
   - `JWT Secret` → SUPABASE_JWT_SECRET

### 1.2 Configurer l'authentification Supabase

1. Va dans **Authentication → Providers**
2. Active **Email** (déjà activé par défaut)
3. (Optionnel) Active **Google** :
   - Va sur https://console.cloud.google.com
   - Crée un projet et active l'API Google OAuth
   - Crée des identifiants OAuth 2.0
   - Ajoute les URLs de callback Supabase
   - Copie Client ID et Secret dans Supabase

### 1.3 Créer un compte Stripe

1. Va sur https://dashboard.stripe.com et crée un compte
2. Active le **mode test** (toggle en haut à droite)
3. Va dans **Developers → API Keys** et note :
   - `Publishable key` → STRIPE_PUBLISHABLE_KEY
   - `Secret key` → STRIPE_SECRET_KEY

### 1.4 Créer les produits Stripe

1. Va dans **Products → Add Product**
2. Crée le produit **"Kickstat Basic"** :
   - Prix : 9,99 € / mois
   - Note le `Price ID` (commence par `price_`) → STRIPE_BASIC_PRICE_ID
3. Crée le produit **"Kickstat Pro"** :
   - Prix : 24,99 € / mois
   - Note le `Price ID` → STRIPE_PRO_PRICE_ID

### 1.5 Configurer le webhook Stripe

1. Va dans **Developers → Webhooks**
2. Clique **"Add endpoint"**
3. URL : `https://ton-domaine.com/api/v1/webhooks/stripe`
   (en dev local, utilise https://ngrok.io ou https://stripe.com/docs/stripe-cli)
4. Sélectionne les événements :
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Note le `Signing secret` → STRIPE_WEBHOOK_SECRET

### 1.6 Créer un bot Telegram

1. Ouvre Telegram et cherche **@BotFather**
2. Envoie `/newbot`
3. Choisis un nom (ex: `Kickstat Bot`)
4. Choisis un username (ex: `kickstat_bot`)
5. Note le token → TELEGRAM_BOT_TOKEN

---

## Étape 2 : Configuration locale

### 2.1 Cloner et préparer

```bash
cd /Users/hatemahmed/football-predictions
```

### 2.2 Configurer le Backend

```bash
# Copier le fichier d'environnement
cp backend/.env.example backend/.env

# Éditer avec tes clés
nano backend/.env
```

Remplis ces valeurs dans `backend/.env` :

```bash
# APPLICATION
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=une-clé-secrète-aléatoire-longue

# DATABASE (utilise SQLite pour dev simple)
DATABASE_URL=sqlite:///./football_predictions.db
# OU PostgreSQL :
# DATABASE_URL=postgresql://user:password@localhost:5432/kickstat

# REDIS (optionnel en dev)
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# API-FOOTBALL (tu as déjà ça)
API_FOOTBALL_KEY=ta-clé-api-football
API_FOOTBALL_HOST=v3.football.api-sports.io

# SUPABASE
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=ton-jwt-secret

# STRIPE
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_BASIC_PRICE_ID=price_xxx
STRIPE_PRO_PRICE_ID=price_xxx

# TELEGRAM
TELEGRAM_BOT_TOKEN=123456:ABC-xxx

# FRONTEND
FRONTEND_URL=http://localhost:3000
```

### 2.3 Configurer le Frontend

```bash
# Copier le fichier d'environnement
cp frontend/.env.example frontend/.env.local

# Éditer avec tes clés
nano frontend/.env.local
```

Remplis ces valeurs dans `frontend/.env.local` :

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_xxx
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Étape 3 : Installation des dépendances

### 3.1 Backend Python

```bash
cd /Users/hatemahmed/football-predictions/backend

# Créer un environnement virtuel
python3 -m venv venv

# Activer l'environnement
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### 3.2 Frontend Node.js

```bash
cd /Users/hatemahmed/football-predictions/frontend

# Installer les dépendances
npm install
```

---

## Étape 4 : Initialiser la base de données

### 4.1 Option A : SQLite (simple pour dev)

```bash
cd /Users/hatemahmed/football-predictions/backend

# Activer l'environnement virtuel
source venv/bin/activate

# Initialiser la base de données
python -c "
from app.core.database import init_db
init_db()
print('Database initialized!')
"
```

### 4.2 Option B : PostgreSQL avec Docker

```bash
cd /Users/hatemahmed/football-predictions

# Lancer PostgreSQL et Redis
docker-compose up -d

# Vérifier que ça tourne
docker-compose ps
```

Puis initialiser la DB :

```bash
cd backend
source venv/bin/activate
python scripts/init_db.py
```

---

## Étape 5 : Lancer le projet

### 5.1 Terminal 1 : Backend

```bash
cd /Users/hatemahmed/football-predictions/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Le backend sera accessible sur : http://localhost:8000
Documentation API : http://localhost:8000/docs

### 5.2 Terminal 2 : Frontend

```bash
cd /Users/hatemahmed/football-predictions/frontend
npm run dev
```

Le frontend sera accessible sur : http://localhost:3000

---

## Étape 6 : Vérifier que tout fonctionne

### 6.1 Tester le backend

```bash
# Health check
curl http://localhost:8000/health

# Devrait retourner : {"status":"healthy","version":"0.1.0"}
```

### 6.2 Tester le frontend

Ouvre http://localhost:3000 dans ton navigateur.
Tu devrais voir la landing page Kickstat.

### 6.3 Tester l'authentification

1. Clique sur "Se connecter"
2. Crée un compte avec ton email
3. Vérifie ton email (check spam)
4. Tu devrais être redirigé vers le dashboard

---

## Étape 7 : Configurer le webhook Telegram (optionnel)

Pour que le bot Telegram reçoive les messages :

### En développement local (avec ngrok)

```bash
# Installer ngrok
brew install ngrok

# Exposer le backend
ngrok http 8000

# Note l'URL https (ex: https://abc123.ngrok.io)
```

Puis configure le webhook :

```bash
curl "http://localhost:8000/api/v1/webhooks/telegram/set-webhook?url=https://abc123.ngrok.io/api/v1/webhooks/telegram"
```

---

## Étape 8 : Synchroniser les données (optionnel)

### Synchroniser les cotes

```bash
cd /Users/hatemahmed/football-predictions/backend
source venv/bin/activate
python scripts/cron/sync_odds.py
```

### Envoyer les alertes

```bash
python scripts/cron/send_alerts.py
```

---

## Structure des fichiers créés

```
football-predictions/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py          # Auth endpoints
│   │   │   ├── subscriptions.py # Stripe endpoints
│   │   │   ├── odds.py          # Edges endpoints
│   │   │   └── webhooks.py      # Webhooks
│   │   ├── models/
│   │   │   └── database.py      # +5 nouveaux modèles
│   │   └── services/
│   │       ├── auth/
│   │       │   ├── supabase.py
│   │       │   └── dependencies.py
│   │       ├── payments/
│   │       │   └── stripe_service.py
│   │       ├── odds/
│   │       │   ├── edge_calculator.py
│   │       │   └── odds_fetcher.py
│   │       └── notifications/
│   │           ├── telegram_bot.py
│   │           └── alert_service.py
│   ├── scripts/cron/
│   │   ├── sync_odds.py
│   │   ├── send_alerts.py
│   │   └── daily_summary.py
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Landing page
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   ├── signup/
│   │   │   │   └── callback/
│   │   │   └── (dashboard)/
│   │   │       ├── layout.tsx
│   │   │       └── dashboard/
│   │   └── lib/
│   │       └── supabase.ts
│   └── .env.example
│
└── SETUP.md                     # Ce guide
```

---

## Dépannage

### Erreur "Module not found"

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### Erreur CORS

Vérifie que `CORS_ORIGINS` dans `backend/.env` contient `http://localhost:3000`

### Erreur Supabase "Invalid JWT"

Vérifie que `SUPABASE_JWT_SECRET` est correct (Settings → API → JWT Settings)

### Le bot Telegram ne répond pas

1. Vérifie que le webhook est configuré
2. Vérifie les logs du backend pour les erreurs

---

## Prochaines étapes

1. **Déployer** sur Vercel (frontend) et Railway (backend)
2. **Configurer** les cron jobs en production
3. **Tester** les paiements avec la carte Stripe de test : `4242 4242 4242 4242`
4. **Personnaliser** les données mock avec de vraies prédictions
