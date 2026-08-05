from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
)

from app.database import Base


class PredictionMemory(Base):
    """
    AI Prediction Memory Storage

    H23.4.5.5.12.X.4.3
    Stores prediction history for learning loop.
    """

    __tablename__ = "prediction_memory"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    router_ip = Column(
        String(45),
        nullable=False,
        index=True,
    )

    prediction_status = Column(
        String(50),
        nullable=False,
    )

    risk_level = Column(
        String(50),
        nullable=False,
    )

    event_code = Column(
        String(100),
        nullable=True,
    )

    confidence_percent = Column(
        Float,
        nullable=True,
    )

    metric = Column(
        String(100),
        nullable=True,
    )

    metric_value = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=lambda:
            datetime.now(timezone.utc),
        nullable=False,
    )
