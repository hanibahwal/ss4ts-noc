from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker


# ==========================================================
# SS4TS Database Configuration
# H23.4.5.5.12.X.4.4
# Persistent AI Memory Database
# ==========================================================


DEFAULT_DATABASE_PATH = (
    "/var/lib/ss4ts-noc/ss4ts.db"
)


DEFAULT_DATABASE_URL = (
    f"sqlite:///{DEFAULT_DATABASE_PATH}"
)


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    DEFAULT_DATABASE_URL,
)


# ==========================================================
# Create SQLite Directory Automatically
# ==========================================================

if DATABASE_URL.startswith("sqlite:///"):

    database_file = DATABASE_URL.replace(
        "sqlite:///",
        "",
    )

    database_path = Path(
        database_file
    )

    database_directory = (
        database_path.parent
    )

    database_directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# SQLAlchemy Engine
# ==========================================================

connect_args = {}

if DATABASE_URL.startswith(
    "sqlite"
):

    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


# ==========================================================
# Database Session
# ==========================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ==========================================================
# Base Model
# ==========================================================

class Base(
    DeclarativeBase
):
    pass


# ==========================================================
# Database Initialization
# ==========================================================
def init_database() -> None:
    """
    Initialize SS4TS database tables.

    Loads all AI memory models before creation.
    """

    # Import models to register tables
    from app.models.prediction_memory import (
        PredictionMemory,
    )

    try:
        from app.models.failure_forecast import (
            FailureForecast,
        )
    except ImportError:
        FailureForecast = None


    Base.metadata.create_all(
        bind=engine
    )
