from __future__ import annotations

import sqlite3

from pathlib import Path

from datetime import datetime, timezone

from uuid import uuid4


from app.models.notification_response_execution_history import (
    NotificationResponseExecutionHistory,
)



class NotificationResponseExecutionHistoryStore:



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
                CREATE TABLE IF NOT EXISTS
                notification_response_execution_history
                (

                    execution_id TEXT PRIMARY KEY,

                    action_id TEXT NOT NULL,

                    action_type TEXT NOT NULL,

                    guard_status TEXT NOT NULL,

                    approved INTEGER NOT NULL,

                    executed INTEGER NOT NULL,

                    result TEXT NOT NULL,

                    created_at TEXT NOT NULL

                )
                """
            )



    def create(
        self,
        action_id: str,
        action_type: str,
        guard_status: str,
        approved: bool,
        executed: bool,
        result: str,
    ) -> NotificationResponseExecutionHistory:


        item = NotificationResponseExecutionHistory(

            execution_id=str(
                uuid4()
            ),

            action_id=action_id,

            action_type=action_type,

            guard_status=guard_status,

            approved=approved,

            executed=executed,

            result=result,

            created_at=datetime.now(
                timezone.utc
            ),

        )


        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO
                notification_response_execution_history
                (
                    execution_id,
                    action_id,
                    action_type,
                    guard_status,
                    approved,
                    executed,
                    result,
                    created_at
                )

                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)

                """,

                (

                    item.execution_id,

                    item.action_id,

                    item.action_type,

                    item.guard_status,

                    int(item.approved),

                    int(item.executed),

                    item.result,

                    item.created_at.isoformat(),

                ),
            )


        return item




    def list_history(
        self,
        limit: int = 50,
    ) -> list[NotificationResponseExecutionHistory]:


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT

                    execution_id,

                    action_id,

                    action_type,

                    guard_status,

                    approved,

                    executed,

                    result,

                    created_at


                FROM notification_response_execution_history

                ORDER BY created_at DESC

                LIMIT ?

                """,
                (
                    limit,
                ),
            ).fetchall()



        return [

            NotificationResponseExecutionHistory(

                execution_id=row[0],

                action_id=row[1],

                action_type=row[2],

                guard_status=row[3],

                approved=bool(row[4]),

                executed=bool(row[5]),

                result=row[6],

                created_at=datetime.fromisoformat(
                    row[7]
                ),

            )

            for row in rows

        ]



    def latest(
        self,
    ):

        result = self.list_history(
            limit=1
        )

        if not result:
            return None

        return result[0]
