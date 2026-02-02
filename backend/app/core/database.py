"""
Database connection and session management.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from app.core.config import get_settings
from app.models.database import Base

settings = get_settings()

# Create engine
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.debug,
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=settings.debug,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables."""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database sessions.

    Usage in FastAPI:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Context manager for database operations."""

    def __init__(self):
        self.session: Session = None

    def __enter__(self) -> Session:
        self.session = SessionLocal()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        self.session.close()


def get_database_manager() -> DatabaseManager:
    """Get a database manager for standalone scripts."""
    return DatabaseManager()
