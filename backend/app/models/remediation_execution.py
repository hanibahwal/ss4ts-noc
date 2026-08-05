from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database import Base



class RemediationExecution(Base):
    """
    H23.4.5.5.12.X.4.5.2.2

    Automated Remediation Execution Engine

    Stores execution history after human approval.
    """


    __tablename__ = "remediation_execution"



    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )



    execution_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )



    approval_id: Mapped[str] = mapped_column(
        String(100),
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



    execution_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="STARTED",
    )



    execution_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )



    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )



    started_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda:
            datetime.now(
                timezone.utc
            ),
    )



    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )



    success: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
