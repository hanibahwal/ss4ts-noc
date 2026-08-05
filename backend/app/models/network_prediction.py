from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    DateTime,
    Text,
)

from app.database import Base


class NetworkPrediction(Base):
    __tablename__ = "network_predictions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_ip = Column(
        String(45),
        index=True,
        nullable=False,
    )

    prediction_time = Column(
        DateTime,
        default=datetime.utcnow,
    )

    risk_score = Column(
        Float,
        default=0,
    )

    confidence = Column(
        Float,
        default=0,
    )

    risk_level = Column(
        String(20),
        default="unknown",
    )

    issue_type = Column(
        String(100),
        nullable=True,
    )

    reason = Column(
        Text,
        nullable=True,
    )
