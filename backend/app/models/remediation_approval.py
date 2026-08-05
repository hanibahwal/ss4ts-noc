from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Text
from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database import Base



class RemediationApproval(Base):
    """
    H23.4.5.5.12.X.4.5.2

    Human Approval & Automated Remediation Engine

    Stores AI generated remediation approval requests.
    """


    __tablename__ = "remediation_approval"


    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )


    approval_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )


    router_ip: Mapped[str] = mapped_column(
        String(45),
        index=True,
        nullable=False,
    )


    action_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


    action_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


    priority: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="MEDIUM",
    )


    risk_level: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="LOW",
    )


    confidence_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
    )


    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="WAITING_APPROVAL",
    )


    approval_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


    approved_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


    approval_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    requested_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda:
            datetime.now(
                timezone.utc
            ),
    )


    approved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )


    executed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )


    execution_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
