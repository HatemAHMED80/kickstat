"""
API v1 Router - Aggregates all endpoint routers.
"""

from fastapi import APIRouter

from .endpoints import admin, matches, teams, predictions, competitions, auth, subscriptions, odds, webhooks

router = APIRouter()

# Existing routers
router.include_router(matches.router, prefix="/matches", tags=["Matches"])
router.include_router(teams.router, prefix="/teams", tags=["Teams"])
router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
router.include_router(competitions.router, prefix="/competitions", tags=["Competitions"])

# New routers for Kickstat web app
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
router.include_router(odds.router, prefix="/odds", tags=["Odds & Edges"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
