# Smart Football Betting API

FastAPI backend for football predictions.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn api.main:app --reload --port 8000
```

## Endpoints

### Health Check
```bash
GET /api/health
```

### Get Predictions
```bash
GET /api/predictions?league=ligue_1&min_edge=3
```

Parameters:
- `league` (optional): Filter by league (`ligue_1`, `premier_league`)
- `min_edge` (optional): Minimum edge threshold (default: 0)

### Train Models
```bash
POST /api/train
```

Trains Dixon-Coles and ELO models on recent historical data.

## Development

API runs on http://localhost:8000
Interactive docs: http://localhost:8000/docs

## Production

Deploy on Railway, Render, or similar Python hosting.
