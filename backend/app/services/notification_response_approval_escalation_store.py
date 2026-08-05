from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.notification_response_approval_escalation import (
    ApprovalEscalationDecision,
)


class NotificationResponseApprovalEscalationStore:
    """
    SS4TS Approval Escalation Audit Store

    H23.4.5.5.12.22.13.7.2

    Stores escalation decisions and delivery status.
    """


    def __init__(
        self,
        database_path: Path,
    ):

        self.database_path = database_path

        self._initialize()



    def _connect(self):

        return sqlite3.connect(
            self.database_path
        )



    def _initialize(self):

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                notification_approval_escalation_audit
                (

                    escalation_id TEXT PRIMARY KEY,

                    approval_id TEXT NOT NULL,

                    risk_score INTEGER NOT NULL,

                    escalation_level TEXT NOT NULL,

                    escalation_target TEXT NOT NULL,

                    reason TEXT NOT NULL,

                    delivery_status TEXT NOT NULL,

                    created_at TEXT NOT NULL,

                    sent_at TEXT

                )
                """
            )



    def create(
        self,
        decision: ApprovalEscalationDecision,
    ):

        escalation_id = str(
            uuid4()
        )


        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO
                notification_approval_escalation_audit
                (
                    escalation_id,
                    approval_id,
                    risk_score,
                    escalation_level,
                    escalation_target,
                    reason,
                    delivery_status,
                    created_at,
                    sent_at
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (

                    escalation_id,

                    decision.approval_id,

                    decision.risk_score,

                    decision.level.value,

                    decision.target.value,

                    decision.reason,

                    "PENDING",

                    decision.created_at.isoformat(),

                    None,

                ),
            )


        return escalation_id



    def mark_sent(
        self,
        escalation_id: str,
    ):

        now = datetime.now(
            timezone.utc
        ).isoformat()


        with self._connect() as connection:

            connection.execute(
                """
                UPDATE
                notification_approval_escalation_audit

                SET
                    delivery_status = ?,
                    sent_at = ?

                WHERE
                    escalation_id = ?
                """,
                (
                    "SENT",
                    now,
                    escalation_id,
                ),
            )



    def mark_failed(
        self,
        escalation_id: str,
    ):


        with self._connect() as connection:

            connection.execute(
                """
                UPDATE
                notification_approval_escalation_audit

                SET
                    delivery_status = ?

                WHERE
                    escalation_id = ?
                """,
                (
                    "FAILED",
                    escalation_id,
                ),
            )



    def get_history(
        self,
        limit: int = 100,
    ):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    *
                FROM
                    notification_approval_escalation_audit

                ORDER BY
                    created_at DESC

                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()


        return [
            {
                "escalation_id": row[0],
                "approval_id": row[1],
                "risk_score": row[2],
                "level": row[3],
                "target": row[4],
                "reason": row[5],
                "status": row[6],
                "created_at": row[7],
                "sent_at": row[8],
            }
            for row in rows
        ]



    def latest(
        self,
    ):

        history = self.get_history(
            limit=1
        )

        return (
            history[0]
            if history
            else None
        )
