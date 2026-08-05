from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from app.database import Base


class ResponseAction(Base):
    """
    SS4TS AI Automated Response Action Model

    H23.4.5.5.12.X.4.6.1

    Stores:
    - Executive decision actions
    - Approval status
    - Execution status
    - Verification results
    """

    __tablename__ = "response_actions"


    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )


    action_id = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )


    router_ip = Column(
        String(50),
        index=True,
        nullable=False,
    )


    decision = Column(
        String(100),
        nullable=False,
    )


    action_type = Column(
        String(100),
        nullable=False,
    )


    action_description = Column(
        Text,
        nullable=True,
    )


    risk_level = Column(
        String(50),
        default="LOW",
    )


    approval_required = Column(
        Integer,
        default=1,
    )


    approval_status = Column(
        String(50),
        default="WAITING_APPROVAL",
    )


    execution_status = Column(
        String(50),
        default="PENDING",
    )


    execution_result = Column(
        Text,
        nullable=True,
    )


    verification_status = Column(
        String(50),
        default="NOT_VERIFIED",
    )


    verification_result = Column(
        Text,
        nullable=True,
    )


    confidence_percent = Column(
        Float,
        default=0,
    )


    created_at = Column(
        String(50),
        default=lambda:
            datetime.now(
                timezone.utc
            ).isoformat(),
    )


    updated_at = Column(
        String(50),
        default=lambda:
            datetime.now(
                timezone.utc
            ).isoformat(),
        onupdate=lambda:
            datetime.now(
                timezone.utc
            ).isoformat(),
    )
