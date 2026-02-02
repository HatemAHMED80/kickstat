# Football Prediction System
## Ligue 1 & Coupes Françaises
### Spécification Technique & Architecture

---

## 1. Résumé Exécutif

Ce document décrit l'architecture d'un système de prédiction de matchs de football utilisant le machine learning. Le système analyse plus de 50 paramètres pour estimer les probabilités de victoire, nul et défaite pour chaque match de Ligue 1 et des coupes françaises.

### Objectifs clés :
- **Précision cible** : 55-60% (vs 33% aléatoire)
- **Couverture** : Ligue 1, Coupe de France, Trophée des Champions
- **Mise à jour** : Données rafraîchies quotidiennement
- **API REST + Interface web responsive**

---

## 2. Matrice des Features

Classification de tous les paramètres par faisabilité, impact et priorité d'implémentation.

### 2.1 Légende Priorités

| Priorité | Description |
|----------|-------------|
| P0 | MVP - Indispensable dès le lancement (données gratuites, impact fort) |
| P1 | V1.1 - Amélioration significative (effort modéré) |
| P2 | V2.0 - Features avancées (scraping NLP, calculs complexes) |
| P3 | Backlog - Données premium coûteuses (Opta, StatsBomb) |

### 2.2 Features par Catégorie

#### Match Context

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Domicile / Extérieur | API-Football | Facile | Très élevé | +15% avantage domicile |
| Aller / Retour | Calendrier API | Facile | Élevé | Score aller = feature clé |
| Élimination directe / Championnat | API-Football | Facile | Élevé | Modèle différent par type |
| Importance du match | Calcul | Moyen | Très élevé | Algorithme custom |
| Pression du résultat | Calcul | Moyen | Élevé | Basé sur classement + objectifs |
| Prolongations / TAB | Historique | Facile | Moyen | Historique équipe aux TAB |

#### Niveau Équipe

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Classement actuel | API-Football | Facile | Très élevé | - |
| Points moyens / match | API-Football | Facile | Élevé | - |
| Différence de buts | API-Football | Facile | Élevé | - |
| ELO / Rating équipe | ClubELO / Calcul | Moyen | Très élevé | Meilleur prédicteur global |
| Valeur marchande effectif | Transfermarkt | Moyen | Élevé | Scraping nécessaire |
| Expérience collective | Transfermarkt | Moyen | Moyen | Âge moyen + sélections |

#### Forme Récente

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Résultats 5 derniers matchs | API-Football | Facile | Très élevé | - |
| Série en cours | API-Football | Facile | Élevé | - |
| Buts marqués récemment | API-Football | Facile | Élevé | - |
| Clean sheets récents | API-Football | Facile | Moyen | - |

#### Mental

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Confiance équipe | Calcul (forme) | Moyen | Élevé | Proxy via résultats |
| Pression médiatique | NLP Presse | Difficile | Moyen | Scraping + sentiment |
| Scandales / Problèmes perso | NLP Presse | Difficile | Variable | Cambriolages, agressions |
| Changement entraîneur | Transfermarkt | Moyen | Élevé | Effet boost initial |

#### Joueurs

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Joueurs clés présents | L'Équipe / API | Moyen | Très élevé | Scraping compos |
| Blessures | Transfermarkt | Moyen | Très élevé | Scraping quotidien |
| Suspensions | API-Football | Facile | Élevé | - |
| Retour de blessure | Transfermarkt | Moyen | Moyen | Risque rechute |
| Retour de sélection | Calendrier FIFA | Facile | Moyen | Fatigue voyages |

#### Physique

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Jours de repos | Calendrier | Facile | Élevé | - |
| Matchs sur 30 jours | Calendrier | Facile | Élevé | - |
| Km parcourus | Opta (€€€) | Très difficile | Élevé | Données premium |
| Distance déplacement | Google Maps API | Facile | Moyen | - |

#### Tactique

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Système de jeu | WhoScored | Moyen | Moyen | 4-3-3, 3-5-2... |
| Style de jeu | Stats avancées | Difficile | Moyen | Possession, contre... |
| Compatibilité tactique | Calcul | Difficile | Moyen | Matchup analysis |

#### Historique H2H

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Résultats confrontations | API-Football | Facile | Moyen | - |
| Buts face à adversaire | API-Football | Facile | Moyen | - |
| Domination psychologique | Calcul H2H | Moyen | Moyen | - |

#### Météo

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Température | OpenWeatherMap | Facile | Faible | Gratuit |
| Pluie / Neige | OpenWeatherMap | Facile | Moyen | Impact jeu au sol |
| Vent | OpenWeatherMap | Facile | Faible | - |
| Qualité pelouse | Manuel / Scraping | Difficile | Moyen | - |
| Pelouse naturelle / synthétique | Base données | Facile | Moyen | - |

#### Arbitrage

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| Style arbitre | Transfermarkt | Moyen | Moyen | - |
| Cartons moyens / match | Transfermarkt | Moyen | Moyen | - |
| Penaltys sifflés | Transfermarkt | Moyen | Moyen | - |

#### Stats Avancées

| Feature | Source | Difficulté | Impact | Notes |
|---------|--------|------------|--------|-------|
| xG / xGA | Understat / FBref | Moyen | Très élevé | Gratuit |
| xG difference | Calcul | Facile | Très élevé | - |
| Possession moyenne | API-Football | Facile | Moyen | - |
| Tirs / Tirs cadrés | API-Football | Facile | Moyen | - |
| Conversion occasions | Calcul | Facile | Élevé | - |

---

## 3. Architecture Technique

### 3.1 Vue d'ensemble

Le système est composé de 4 couches principales : collecte de données, traitement, modèle ML, et API/Frontend.

| Couche | Technologies & Responsabilités |
|--------|-------------------------------|
| Data Collection | Python scrapers (BeautifulSoup, Selenium) + API calls (requests) + Cron jobs |
| Data Processing | PostgreSQL (stockage) + Redis (cache) + Pandas (transformation) + dbt (pipelines) |
| ML Engine | scikit-learn (XGBoost, Random Forest) + MLflow (tracking) + Feature Store |
| API & Frontend | FastAPI (REST) + Next.js (web) + React Native (mobile optionnel) |

### 3.2 Sources de Données

| Source | Données | Coût | Méthode |
|--------|---------|------|---------|
| API-Football | Résultats, classements, stats matchs, calendrier | Gratuit (100 req/jour) | API REST |
| Transfermarkt | Blessures, valeurs, arbitres, entraîneurs | Gratuit | Scraping |
| Understat / FBref | xG, xGA, stats avancées | Gratuit | Scraping |
| L'Équipe / RMC | Compos, news, scandales | Gratuit | Scraping + NLP |
| OpenWeatherMap | Météo (température, pluie, vent) | Gratuit (1000 req/jour) | API REST |
| ClubELO | Ratings ELO historiques | Gratuit | CSV download |

---

## 4. Algorithmes de Calcul

### 4.1 Score d'Importance du Match

Formule composite intégrant plusieurs facteurs contextuels :

```
importance = w1×(écart_objectif) + w2×(journée_factor) + w3×(rivalité) + w4×(élimination) + w5×(score_aller)
```

| Variable | Description | Valeurs |
|----------|-------------|---------|
| écart_objectif | Distance aux places qualificatives/relégation | 0-100 (100 = lutte directe) |
| journée_factor | Position dans la saison | J1-10: 0.3 \| J11-30: 0.5 \| J31+: 1.0 |
| rivalité | Derby ou rivalité historique | 0 (normal) \| 0.5 (régional) \| 1 (derby) |
| élimination | Match à élimination directe | 0 (championnat) \| 1 (coupe) |
| score_aller | Contexte match retour | f(écart buts aller) |

### 4.2 Score de Perturbation (NLP)

Analyse sentiment des articles de presse pour détecter les perturbations :

| Type d'événement | Score | Exemple |
|------------------|-------|---------|
| Cambriolage / Agression | -0.8 | Domicile joueur cambriolé pendant match |
| Conflit avec coach | -0.6 | Mise à l'écart, clash médiatique |
| Problème familial | -0.5 | Décès proche, divorce |
| Rumeur transfert | -0.3 | Négociations mercato |
| Retour sélection (positif) | +0.2 | Rappelé en équipe nationale |
| Événement heureux | +0.3 | Naissance enfant, mariage |

### 4.3 Modèle de Prédiction

Ensemble de modèles combinés pour robustesse :

1. **XGBoost** : Capture les interactions complexes entre features (poids: 0.5)
2. **Logistic Regression** : Baseline interprétable, calibration probabilités (poids: 0.3)
3. **Random Forest** : Robustesse au bruit, feature importance (poids: 0.2)

**Output du modèle :**
- P(victoire équipe domicile)
- P(match nul)
- P(victoire équipe extérieur)
- Confidence score (0-1)
- P(prolongations) si élimination directe
- P(victoire TAB équipe A/B) si applicable

---

## 5. Roadmap d'Implémentation

### Phase 1 : MVP (4-6 semaines)
**Budget: 0€ | Précision cible: 50-55%**

- Intégration API-Football (résultats, classements, calendrier)
- Calcul ELO maison basé sur historique
- Features forme récente (5 derniers matchs)
- Scraper Transfermarkt (blessures)
- Modèle XGBoost simple (~25 features)
- API FastAPI basique
- Frontend minimal (Next.js)

### Phase 2 : Enrichissement (6-8 semaines)
**Budget: ~50€/mois | Précision cible: 55-58%**

- xG/xGA via Understat/FBref
- Météo (OpenWeatherMap)
- Stats arbitres
- Détection changements entraîneur
- Système de jeu (scraping WhoScored)
- Score importance match
- API-Football Pro (plus de requêtes)

### Phase 3 : Intelligence (8-12 semaines)
**Budget: ~150€/mois | Précision cible: 58-62%**

- Pipeline NLP presse (sentiment analysis)
- Détection scandales/problèmes personnels
- Analyse compatibilité tactique
- Modèle spécifique matchs à élimination
- Prédiction prolongations/TAB
- Feature store temps réel

### Phase 4 : Premium (Optionnel)
**Budget: 500€+/mois | Précision cible: 62-65%**

- Données Opta/StatsBomb (km parcourus, pressing)
- Tracking joueurs en temps réel
- Deep learning (LSTM séquences matchs)
- API commerciale pour B2B

---

## 6. Spécification API

### 6.1 Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | /api/v1/matches/upcoming | Liste des prochains matchs avec prédictions |
| GET | /api/v1/matches/{id}/prediction | Prédiction détaillée pour un match |
| GET | /api/v1/teams/{id}/stats | Statistiques et forme d'une équipe |
| GET | /api/v1/teams/{id}/players | Effectif avec disponibilités |
| GET | /api/v1/h2h/{team1_id}/{team2_id} | Historique confrontations |
| GET | /api/v1/competitions/{id}/standings | Classement d'une compétition |
| POST | /api/v1/predictions/simulate | Simulation avec paramètres custom |

### 6.2 Exemple de Réponse

```http
GET /api/v1/matches/12345/prediction
```

```json
{
  "match_id": 12345,
  "home_team": "PSG",
  "away_team": "OM",
  "kickoff": "2025-02-15T21:00:00Z",
  "competition": "Ligue 1",
  "matchday": 22,
  "prediction": {
    "home_win": 0.52,
    "draw": 0.24,
    "away_win": 0.24,
    "confidence": 0.78
  },
  "factors": {
    "home_advantage": "+12%",
    "form_difference": "+8% PSG",
    "injuries_impact": "-3% PSG (Mbappé doubtful)",
    "h2h_factor": "neutral",
    "importance": "high (title race)"
  }
}
```

---

## 7. Schéma Base de Données

### 7.1 Tables Principales

| Table | Colonnes clés |
|-------|---------------|
| teams | id, name, short_name, logo_url, stadium_id, elo_rating, market_value |
| players | id, team_id, name, position, market_value, injury_status, return_date |
| matches | id, home_team_id, away_team_id, kickoff, competition_id, matchday, venue_id |
| match_stats | match_id, team_id, goals, xg, possession, shots, passes, corners |
| predictions | match_id, home_win_prob, draw_prob, away_win_prob, confidence, created_at |
| news_articles | id, source, title, content, published_at, sentiment_score, entities[] |
| weather_forecasts | match_id, temperature, precipitation, wind_speed, humidity, fetched_at |
| referees | id, name, avg_fouls, avg_yellows, avg_reds, avg_penalties, home_bias |

---

## 8. Risques & Limitations

### 8.1 Limitations Inhérentes

- **Part incompressible de hasard** : erreurs arbitrales, blessures en match, buts contre son camp (~15-20% des résultats)
- **Données privées inaccessibles** : GPS tracking clubs, état psychologique réel, consignes tactiques
- **Décalage temporel** : compositions confirmées seulement 1h avant le match

### 8.2 Risques Techniques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| API rate limits | Données incomplètes ou retardées | Cache agressif, multiple sources |
| Scraping bloqué | Perte de données blessures/news | Rotation proxies, backup sources |
| Overfitting | Modèle performant sur historique mais pas en live | Cross-validation, holdout set |
| Data drift | Changements de règles ou style de jeu | Monitoring, retraining mensuel |

### 8.3 Avertissement Légal

> *Ce système est fourni à titre informatif uniquement. Les prédictions ne constituent pas des conseils de paris. Les performances passées ne garantissent pas les résultats futurs. L'utilisation pour des paris sportifs se fait aux risques et périls de l'utilisateur.*

---

## 9. Prochaines Étapes

**Actions immédiates pour démarrer le MVP :**

1. Créer compte API-Football (gratuit) et tester les endpoints
2. Setup repository Git avec structure projet (Python backend + Next.js frontend)
3. Développer scraper Transfermarkt pour blessures Ligue 1
4. Collecter 3 saisons d'historique pour entraînement modèle
5. Implémenter calcul ELO basique
6. Premier modèle XGBoost avec ~15 features
7. Valider sur saison 2024-2025 en cours

---

*— Fin du document —*
