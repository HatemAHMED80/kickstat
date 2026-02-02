#!/usr/bin/env python3
"""
Initialize database and create all tables.

Usage:
    python scripts/init_db.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.core import init_db


def main():
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully!")


if __name__ == "__main__":
    main()
