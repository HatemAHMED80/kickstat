#!/bin/bash
# daily_predictions.sh — Pipeline quotidien Kickstat
#
# Orchestre le pipeline complet:
#   1. Génération des prédictions (modèles ML + fixtures + cotes)
#   2. Sync prédictions → Supabase (en attente)
#   3. Résolution des paris passés (fetch résultats)
#   4. Sync historique → Supabase (résolus)
#
# Usage:
#   bash scripts/daily_predictions.sh              # Normal (demain)
#   bash scripts/daily_predictions.sh --today      # Matchs d'aujourd'hui
#   bash scripts/daily_predictions.sh --date 2026-03-05

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date "+%Y-%m-%d_%H-%M")
LOG_FILE="$LOG_DIR/predictions_$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

log() {
    local msg="$(date '+%Y-%m-%d %H:%M:%S') | $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

log "=== KICKSTAT DAILY PREDICTIONS ==="
log "Project root: $PROJECT_ROOT"

# Activate venv
VENV="$PROJECT_ROOT/venv/bin/activate"
if [ -f "$VENV" ]; then
    source "$VENV"
    log "Venv activated: $(which python3)"
else
    log "WARNING: No venv found, using system Python"
fi

# Pass through any arguments (--today, --date, --force-train)
EXTRA_ARGS="${@}"

# ── Step 1: Generate predictions ──────────────────────────────────
log "Step 1/4: Generating predictions..."
START=$(date +%s)

if python3 "$PROJECT_ROOT/generate_predictions_json.py" $EXTRA_ARGS 2>&1 | tee -a "$LOG_FILE"; then
    ELAPSED=$(( $(date +%s) - START ))
    log "Step 1 OK (${ELAPSED}s)"
else
    log "ERROR: generate_predictions_json.py failed"
    exit 1
fi

# Verify output
PRED_FILE="$PROJECT_ROOT/web/public/predictions.json"
if [ -f "$PRED_FILE" ]; then
    COUNT=$(python3 -c "import json; d=json.load(open('$PRED_FILE')); print(len(d.get('predictions',d)))")
    SIZE=$(du -h "$PRED_FILE" | cut -f1)
    log "  predictions.json: $COUNT predictions ($SIZE)"
else
    log "ERROR: predictions.json not found"
    exit 1
fi

# ── Step 2: Sync predictions → Supabase ───────────────────────────
log "Step 2/4: Syncing predictions to Supabase..."
if python3 "$PROJECT_ROOT/scripts/sync_predictions.py" 2>&1 | tee -a "$LOG_FILE"; then
    log "Step 2 OK"
else
    log "WARNING: sync_predictions.py failed (non-fatal)"
fi

# ── Step 3: Fetch results for past predictions ────────────────────
log "Step 3/4: Fetching results..."
if python3 "$PROJECT_ROOT/scripts/fetch_results.py" 2>&1 | tee -a "$LOG_FILE"; then
    log "Step 3 OK"
else
    log "WARNING: fetch_results.py failed (non-fatal)"
fi

# ── Step 4: Sync history → Supabase ───────────────────────────────
log "Step 4/4: Syncing history to Supabase..."
if python3 "$PROJECT_ROOT/scripts/sync_history.py" --seed 2>&1 | tee -a "$LOG_FILE"; then
    log "Step 4 OK"
else
    log "WARNING: sync_history.py failed (non-fatal)"
fi

# ── Clean old logs (keep 30 days) ─────────────────────────────────
find "$LOG_DIR" -name "predictions_*.log" -mtime +30 -delete 2>/dev/null || true

log "=== DONE ==="
