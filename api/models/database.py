"""
Database models for Football Prediction System.
SQLAlchemy ORM models matching the specification schema.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Competition(Base):
    """Competitions: Ligue 1, Coupe de France, Trophée des Champions"""

    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, unique=True, index=True)  # API-Football ID
    name = Column(String(100), nullable=False)
    short_name = Column(String(20))
    country = Column(String(50), default="France")
    type = Column(String(20))  # league, cup
    season = Column(Integer)
    logo_url = Column(String(255))

    matches = relationship("Match", back_populates="competition")
    standings = relationship("Standing", back_populates="competition")


class Team(Base):
    """Football teams"""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, unique=True, index=True)  # API-Football ID
    name = Column(String(100), nullable=False)
    short_name = Column(String(30))
    code = Column(String(5))  # PSG, OM, OL...
    logo_url = Column(String(255))
    stadium_id = Column(Integer, ForeignKey("stadiums.id"))

    # Ratings & values
    elo_rating = Column(Float, default=1500.0)
    market_value = Column(Float)  # in millions €

    # Metadata
    founded = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stadium = relationship("Stadium", back_populates="teams")
    players = relationship("Player", back_populates="team")
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")


class Stadium(Base):
    """Stadiums / Venues"""

    __tablename__ = "stadiums"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, unique=True, index=True)
    name = Column(String(100), nullable=False)
    city = Column(String(50))
    capacity = Column(Integer)
    surface = Column(String(20))  # grass, artificial
    latitude = Column(Float)
    longitude = Column(Float)

    teams = relationship("Team", back_populates="stadium")
    matches = relationship("Match", back_populates="venue")


class Player(Base):
    """Players with injury/availability tracking"""

    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, unique=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True)

    name = Column(String(100), nullable=False)
    firstname = Column(String(50))
    lastname = Column(String(50))
    position = Column(String(30))  # Goalkeeper, Defender, Midfielder, Attacker
    number = Column(Integer)

    birth_date = Column(DateTime)
    nationality = Column(String(50))
    height = Column(Integer)  # cm
    weight = Column(Integer)  # kg

    market_value = Column(Float)  # millions €

    # Availability
    injury_status = Column(String(50))  # fit, injured, doubtful
    injury_type = Column(String(100))
    return_date = Column(DateTime)
    suspended = Column(Boolean, default=False)
    suspension_end = Column(DateTime)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    team = relationship("Team", back_populates="players")

    __table_args__ = (Index("ix_players_team_position", "team_id", "position"),)


class Match(Base):
    """Matches with results"""

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, unique=True, index=True)

    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), index=True)
    venue_id = Column(Integer, ForeignKey("stadiums.id"))
    referee_id = Column(Integer, ForeignKey("referees.id"))

    kickoff = Column(DateTime, nullable=False, index=True)
    matchday = Column(Integer)  # Journée for league, round for cup
    round_name = Column(String(50))  # "32èmes", "Quart de finale"...

    # Status
    status = Column(String(20), default="scheduled")  # scheduled, live, finished, postponed

    # Results (null if not finished)
    home_score = Column(Integer)
    away_score = Column(Integer)
    home_score_ht = Column(Integer)  # Half-time
    away_score_ht = Column(Integer)

    # Extra time / Penalties (for cups)
    extra_time = Column(Boolean, default=False)
    home_score_et = Column(Integer)
    away_score_et = Column(Integer)
    penalties = Column(Boolean, default=False)
    home_penalties = Column(Integer)
    away_penalties = Column(Integer)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    competition = relationship("Competition", back_populates="matches")
    venue = relationship("Stadium", back_populates="matches")
    referee = relationship("Referee", back_populates="matches")
    stats = relationship("MatchStats", back_populates="match")
    prediction = relationship("Prediction", back_populates="match", uselist=False)
    weather = relationship("WeatherForecast", back_populates="match", uselist=False)

    __table_args__ = (
        Index("ix_matches_kickoff_competition", "kickoff", "competition_id"),
        Index("ix_matches_teams", "home_team_id", "away_team_id"),
    )


class MatchStats(Base):
    """Detailed match statistics per team"""

    __tablename__ = "match_stats"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    # Basic stats
    goals = Column(Integer)
    shots = Column(Integer)
    shots_on_target = Column(Integer)
    possession = Column(Float)  # percentage
    passes = Column(Integer)
    pass_accuracy = Column(Float)

    # Advanced stats
    xg = Column(Float)  # Expected goals
    xga = Column(Float)  # Expected goals against
    corners = Column(Integer)
    fouls = Column(Integer)
    yellow_cards = Column(Integer)
    red_cards = Column(Integer)
    offsides = Column(Integer)

    match = relationship("Match", back_populates="stats")

    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="uq_match_team_stats"),
    )


class Standing(Base):
    """League standings"""

    __tablename__ = "standings"

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    position = Column(Integer, nullable=False)
    played = Column(Integer, default=0)
    won = Column(Integer, default=0)
    drawn = Column(Integer, default=0)
    lost = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    goal_difference = Column(Integer, default=0)
    points = Column(Integer, default=0)

    form = Column(String(10))  # "WWDLW"

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    competition = relationship("Competition", back_populates="standings")

    __table_args__ = (
        UniqueConstraint("competition_id", "team_id", name="uq_competition_team_standing"),
        Index("ix_standings_position", "competition_id", "position"),
    )


class Prediction(Base):
    """Model predictions for matches"""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), unique=True, nullable=False)

    # Probabilities
    home_win_prob = Column(Float, nullable=False)
    draw_prob = Column(Float, nullable=False)
    away_win_prob = Column(Float, nullable=False)
    confidence = Column(Float)  # 0-1

    # For cup matches
    extra_time_prob = Column(Float)
    home_pen_win_prob = Column(Float)
    away_pen_win_prob = Column(Float)

    # Model info
    model_version = Column(String(50))
    features_used = Column(JSON)  # List of features used
    feature_importances = Column(JSON)  # Top contributing factors

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    match = relationship("Match", back_populates="prediction")


class Referee(Base):
    """Referees with statistics"""

    __tablename__ = "referees"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, unique=True, index=True)
    name = Column(String(100), nullable=False)
    nationality = Column(String(50))

    # Statistics
    matches_officiated = Column(Integer, default=0)
    avg_fouls_per_match = Column(Float)
    avg_yellow_cards = Column(Float)
    avg_red_cards = Column(Float)
    avg_penalties = Column(Float)
    home_win_rate = Column(Float)  # Potential home bias

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    matches = relationship("Match", back_populates="referee")


class WeatherForecast(Base):
    """Weather conditions for matches"""

    __tablename__ = "weather_forecasts"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), unique=True, nullable=False)

    temperature = Column(Float)  # Celsius
    feels_like = Column(Float)
    humidity = Column(Integer)  # percentage
    precipitation = Column(Float)  # mm
    precipitation_prob = Column(Float)  # percentage
    wind_speed = Column(Float)  # km/h
    wind_direction = Column(Integer)  # degrees
    weather_code = Column(String(20))  # clear, clouds, rain, snow...
    weather_description = Column(String(100))

    fetched_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="weather")


class NewsArticle(Base):
    """News articles for NLP analysis (Phase 3)"""

    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True)

    source = Column(String(50))  # lequipe, rmcsport...
    url = Column(String(500), unique=True)
    title = Column(String(300), nullable=False)
    content = Column(Text)

    published_at = Column(DateTime, index=True)

    # NLP results
    sentiment_score = Column(Float)  # -1 to 1
    entities = Column(JSON)  # Detected players, teams
    perturbation_score = Column(Float)  # Impact score
    perturbation_type = Column(String(50))  # injury, scandal, transfer...

    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_news_published", "published_at", "source"),)


class PlayerSeasonStats(Base):
    """Player performance statistics per season - PERFORMANCE BASED ONLY"""

    __tablename__ = "player_season_stats"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    season = Column(Integer, nullable=False)  # e.g., 2024

    # Appearances
    matches_played = Column(Integer, default=0)
    matches_started = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)

    # Goals & Assists (PERFORMANCE)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)

    # Shooting (PERFORMANCE)
    shots_total = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)

    # Passing (PERFORMANCE)
    passes_total = Column(Integer, default=0)
    passes_accurate = Column(Integer, default=0)
    key_passes = Column(Integer, default=0)

    # Defending (PERFORMANCE)
    tackles = Column(Integer, default=0)
    interceptions = Column(Integer, default=0)
    blocks = Column(Integer, default=0)

    # Duels (KEY PLAYER METRIC)
    duels_total = Column(Integer, default=0)
    duels_won = Column(Integer, default=0)

    # Dribbles
    dribbles_attempts = Column(Integer, default=0)
    dribbles_success = Column(Integer, default=0)

    # Goalkeeper (PERFORMANCE)
    saves = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    clean_sheets = Column(Integer, default=0)

    # Discipline
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)

    # Calculated metrics
    goals_per_90 = Column(Float)
    assists_per_90 = Column(Float)
    impact_score = Column(Float)  # Calculated player impact

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season"),
    )


class EloHistory(Base):
    """Historical ELO ratings for teams"""

    __tablename__ = "elo_history"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))

    elo_before = Column(Float, nullable=False)
    elo_after = Column(Float, nullable=False)
    elo_change = Column(Float)

    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_elo_team_date", "team_id", "recorded_at"),)


# =============================================================================
# USER & SUBSCRIPTION MODELS (Kickstat Web App)
# =============================================================================


class User(Base):
    """Users synced from Supabase Auth"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)  # Supabase UUID
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(100))

    # Subscription
    subscription_tier = Column(String(20), default="free")  # free, basic, pro
    subscription_status = Column(String(20), default="inactive")  # active, inactive, cancelled
    stripe_customer_id = Column(String(255), unique=True, index=True)
    stripe_subscription_id = Column(String(255))
    subscription_ends_at = Column(DateTime)

    # Telegram
    telegram_chat_id = Column(String(50), index=True)
    telegram_username = Column(String(100))
    telegram_alerts_enabled = Column(Boolean, default=False)
    telegram_connect_token = Column(String(64))  # Temporary token for connection

    # Preferences
    preferred_leagues = Column(JSON, default=list)  # [61, 66] for Ligue 1, Ligue 2
    min_edge_threshold = Column(Float, default=5.0)  # Minimum edge % for alerts
    alert_hours_before = Column(Integer, default=24)  # Hours before match

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)

    # Relationships
    purchases = relationship("MatchPurchase", back_populates="user")
    alerts = relationship("AlertHistory", back_populates="user")


class MatchPurchase(Base):
    """Individual match purchases (0.99 EUR per match)"""

    __tablename__ = "match_purchases"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)

    stripe_payment_intent_id = Column(String(255), unique=True)
    amount_cents = Column(Integer, default=99)  # 0.99 EUR in cents
    currency = Column(String(3), default="eur")
    status = Column(String(20), default="pending")  # pending, completed, refunded

    purchased_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="purchases")
    match = relationship("Match")

    __table_args__ = (
        UniqueConstraint("user_id", "match_id", name="uq_user_match_purchase"),
    )


class MatchOdds(Base):
    """Bookmaker odds for matches"""

    __tablename__ = "match_odds"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    bookmaker = Column(String(50), nullable=False)  # bet365, unibet, winamax...

    # Decimal odds
    home_win_odds = Column(Float)
    draw_odds = Column(Float)
    away_win_odds = Column(Float)

    # Over/Under 2.5 goals
    over_25_odds = Column(Float)
    under_25_odds = Column(Float)

    # BTTS (Both Teams To Score)
    btts_yes_odds = Column(Float)
    btts_no_odds = Column(Float)

    # Implied probabilities (calculated from odds)
    home_win_implied = Column(Float)
    draw_implied = Column(Float)
    away_win_implied = Column(Float)

    fetched_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match")

    __table_args__ = (
        Index("ix_odds_match_bookmaker", "match_id", "bookmaker"),
        UniqueConstraint("match_id", "bookmaker", name="uq_match_bookmaker"),
    )


class EdgeCalculation(Base):
    """Calculated edge (model probability vs bookmaker probability)"""

    __tablename__ = "edge_calculations"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"))

    # Market type
    market = Column(String(30), nullable=False)  # 1x2_home, 1x2_draw, 1x2_away, over_25, btts_yes...

    # Edge calculation
    model_probability = Column(Float, nullable=False)
    bookmaker_probability = Column(Float, nullable=False)
    edge_percentage = Column(Float, nullable=False)  # (model - book) / book * 100

    # Best odds found
    best_odds = Column(Float)
    bookmaker_name = Column(String(50))

    # Risk classification
    risk_level = Column(String(10))  # safe, medium, risky

    # Kelly criterion stake suggestion (fraction of bankroll)
    kelly_stake = Column(Float)

    # Confidence score (0-100)
    confidence = Column(Float)

    calculated_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match")
    prediction = relationship("Prediction")

    __table_args__ = (
        Index("ix_edge_match_market", "match_id", "market"),
        Index("ix_edge_percentage", "edge_percentage"),
    )


class AlertHistory(Base):
    """History of sent alerts"""

    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    edge_id = Column(Integer, ForeignKey("edge_calculations.id"))

    channel = Column(String(20), nullable=False)  # telegram, email
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered = Column(Boolean, default=True)
    error_message = Column(String(255))

    user = relationship("User", back_populates="alerts")
    match = relationship("Match")
    edge = relationship("EdgeCalculation")
