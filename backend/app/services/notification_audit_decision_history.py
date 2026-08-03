from __future__ import annotations

import json

import sqlite3

from pathlib import Path

from datetime import datetime, timezone

from uuid import uuid4


from app.models.notification_audit_decision_history import (
    NotificationDecisionHistory,
)





class NotificationDecisionHistoryStore:


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





    def _initialize(
        self,
    ):

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_decision_history
                (
                    decision_id TEXT PRIMARY KEY,

                    decision TEXT NOT NULL,

                    confidence INTEGER NOT NULL,

                    risk_level TEXT NOT NULL,

                    risk_score INTEGER NOT NULL,

                    reason TEXT NOT NULL,

                    actions TEXT NOT NULL,

                    generated_at TEXT NOT NULL
                )
                """
            )





    def create_history(
        self,
        decision: str,
        confidence: int,
        risk_level: str,
        risk_score: int,
        reason: str,
        actions: list[str],
    ) -> NotificationDecisionHistory:


        item = NotificationDecisionHistory(

            decision_id=str(
                uuid4()
            ),

            decision=decision,

            confidence=confidence,

            risk_level=risk_level,

            risk_score=risk_score,

            reason=reason,

            actions=actions,

            generated_at=datetime.now(
                timezone.utc
            ),

        )



        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO notification_decision_history
                (
                    decision_id,
                    decision,
                    confidence,
                    risk_level,
                    risk_score,
                    reason,
                    actions,
                    generated_at
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.decision_id,

                    item.decision,

                    item.confidence,

                    item.risk_level,

                    item.risk_score,

                    item.reason,

                    json.dumps(
                        item.actions
                    ),

                    item.generated_at.isoformat(),

                ),
            )



        return item





    def list_history(
        self,
        limit: int = 50,
    ) -> list[NotificationDecisionHistory]:


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    decision_id,
                    decision,
                    confidence,
                    risk_level,
                    risk_score,
                    reason,
                    actions,
                    generated_at

                FROM notification_decision_history

                ORDER BY generated_at DESC

                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()



        return [

            NotificationDecisionHistory(

                decision_id=row[0],

                decision=row[1],

                confidence=row[2],

                risk_level=row[3],

                risk_score=row[4],

                reason=row[5],

                actions=json.loads(
                    row[6]
                ),

                generated_at=datetime.fromisoformat(
                    row[7]
                ),

            )

            for row in rows

        ]





    def latest(
        self,
    ) -> NotificationDecisionHistory | None:


        result = self.list_history(
            limit=1
        )


        if not result:

            return None


        return result[0]
