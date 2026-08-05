from __future__ import annotations

import sqlite3

from datetime import datetime, timezone

from pathlib import Path

from uuid import uuid4


class NotificationResponseApprovalEscalationAuditStore:
    """
    Audit trail storage for notification approval escalations.

    Tracks:
    - Risk score changes
    - Priority escalation
    - Escalation destination
    - Notification channel
    - Notification status
    - Acknowledgement history
    """


    def __init__(
        self,
        database_path: str | Path = "notifications.sqlite3",
    ):

        self.database_path = Path(database_path)

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
                notification_response_approval_escalation_audit
                (

                    escalation_id TEXT PRIMARY KEY,

                    approval_id TEXT NOT NULL,

                    execution_id TEXT,

                    risk_score INTEGER NOT NULL,

                    priority_before TEXT,

                    priority_after TEXT,

                    escalation_level TEXT NOT NULL,

                    notification_channel TEXT,

                    destination TEXT,

                    notification_status TEXT,

                    acknowledged_by TEXT,

                    created_at TEXT NOT NULL,

                    acknowledged_at TEXT

                )
                """
            )


    def create_record(
        self,
        approval_id: str,
        execution_id: str | None,
        risk_score: int,
        priority_before: str,
        priority_after: str,
        escalation_level: str,
        notification_channel: str,
        destination: str,
        notification_status: str = "pending",
    ):


        escalation_id = str(
            uuid4()
        )


        created_at = datetime.now(
            timezone.utc
        ).isoformat()


        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO
                notification_response_approval_escalation_audit
                (

                    escalation_id,

                    approval_id,

                    execution_id,

                    risk_score,

                    priority_before,

                    priority_after,

                    escalation_level,

                    notification_channel,

                    destination,

                    notification_status,

                    acknowledged_by,

                    created_at,

                    acknowledged_at

                )

                VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?)

                """,

                (

                    escalation_id,

                    approval_id,

                    execution_id,

                    risk_score,

                    priority_before,

                    priority_after,

                    escalation_level,

                    notification_channel,

                    destination,

                    notification_status,

                    None,

                    created_at,

                    None,

                )

            )


        return self.get(
            escalation_id
        )


    def acknowledge(
        self,
        escalation_id: str,
        acknowledged_by: str,
    ):


        acknowledged_at = datetime.now(
            timezone.utc
        ).isoformat()


        with self._connect() as connection:

            connection.execute(
                """
                UPDATE
                notification_response_approval_escalation_audit

                SET

                    acknowledged_by=?,

                    acknowledged_at=?,

                    notification_status='acknowledged'

                WHERE

                    escalation_id=?

                """,

                (

                    acknowledged_by,

                    acknowledged_at,

                    escalation_id,

                )

            )


        return self.get(
            escalation_id
        )


    def get(
        self,
        escalation_id: str,
    ):


        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT *

                FROM
                notification_response_approval_escalation_audit

                WHERE escalation_id=?

                """,

                (
                    escalation_id,
                )

            ).fetchone()


        return self._row_to_dict(
            row
        )


    def list_history(
        self,
        limit: int = 100,
    ):


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT *

                FROM
                notification_response_approval_escalation_audit

                ORDER BY
                created_at DESC

                LIMIT ?

                """,

                (
                    limit,
                )

            ).fetchall()


        return [

            self._row_to_dict(
                row
            )

            for row in rows

        ]


    def statistics(self):

        with self._connect() as connection:


            total = connection.execute(
                """
                SELECT COUNT(*)

                FROM
                notification_response_approval_escalation_audit

                """
            ).fetchone()[0]


            critical = connection.execute(
                """
                SELECT COUNT(*)

                FROM
                notification_response_approval_escalation_audit

                WHERE escalation_level='critical'

                """
            ).fetchone()[0]


            executive = connection.execute(
                """
                SELECT COUNT(*)

                FROM
                notification_response_approval_escalation_audit

                WHERE escalation_level='executive'

                """
            ).fetchone()[0]


            noc = connection.execute(
                """
                SELECT COUNT(*)

                FROM
                notification_response_approval_escalation_audit

                WHERE escalation_level='noc'

                """
            ).fetchone()[0]


        return {

            "total": total,

            "critical": critical,

            "executive": executive,

            "noc": noc,

        }


    def _row_to_dict(
        self,
        row,
    ):


        if not row:

            return None


        return {

            "escalation_id": row[0],

            "approval_id": row[1],

            "execution_id": row[2],

            "risk_score": row[3],

            "priority_before": row[4],

            "priority_after": row[5],

            "escalation_level": row[6],

            "notification_channel": row[7],

            "destination": row[8],

            "notification_status": row[9],

            "acknowledged_by": row[10],

            "created_at": row[11],

            "acknowledged_at": row[12],

        }
