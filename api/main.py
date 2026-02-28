"""FastAPI backend for Smart Football Betting predictions."""

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import predictions, health, auth, subscriptions, webhooks

app = FastAPI(
    title="Smart Football Betting API",
    description="AI-powered football predictions with Dixon-Coles + ELO ensemble",
    version="1.0.0"
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(predictions.router, prefix="/api", tags=["predictions"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["subscriptions"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])

@app.get("/")
async def root():
    return {
        "message": "Smart Football Betting API",
        "docs": "/docs",
        "health": "/api/health"
    }
