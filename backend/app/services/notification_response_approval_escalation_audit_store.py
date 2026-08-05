from __future__ import annotations

import sqlite3

from datetime import datetime, timezone

from uuid import uuid4


class NotificationResponseApprovalEscalationAuditStore:
    """
    SS4TS Escalation Audit Persistence

    H23.4.5.5.12.22.13.7.8.5.1

    Store:
    - escalation events
    - target
    - risk
    - notification status
    """



    def __init__(
        self,
        database_path: str,
    ):

        self.database_path = database_path

        self._initialize()



    def _connect(self):

        return sqlite3.connect(
            self.database_path
        )



    def _initialize(self):

        with self._connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                notification_escalation_audit
                (

                    event_id TEXT PRIMARY KEY,

                    approval_id TEXT NOT NULL,

                    risk_score INTEGER NOT NULL,

                    level TEXT NOT NULL,

                    target TEXT NOT NULL,

                    reason TEXT NOT NULL,

                    telegram_status TEXT NOT NULL,

                    created_at TEXT NOT NULL

                )
                """
            )



    def save(
        self,
        decision,
        telegram_status: str,
    ):


        event_id = str(
            uuid4()
        )


        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO notification_escalation_audit
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,

                (

                    event_id,

                    decision.approval_id,

                    decision.risk_score,

                    decision.level.value,

                    decision.target.value,

                    decision.reason,

                    telegram_status,

                    datetime.now(
                        timezone.utc
                    ).isoformat(),

                )
            )


        return event_id



    def history(
        self,
        limit: int = 1000,
    ):


        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM notification_escalation_audit
                ORDER BY created_at DESC
                LIMIT ?
                """,

                (limit,)
            ).fetchall()


        return [

            {

                "event_id": row[0],

                "approval_id": row[1],

                "risk_score": row[2],

                "level": row[3],

                "target": row[4],

                "reason": row[5],

                "telegram_status": row[6],

                "created_at": row[7],

            }

            for row in rows

        ]
