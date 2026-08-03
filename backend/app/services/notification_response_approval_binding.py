from __future__ import annotations

import sqlite3

from pathlib import Path

from datetime import datetime, timezone

from uuid import uuid4


from app.models.notification_response_approval_binding import (
    NotificationResponseApprovalBinding,
    ApprovalExecutionStatus,
)



class NotificationResponseApprovalBindingStore:



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
                notification_response_approval_binding
                (

                    binding_id TEXT PRIMARY KEY,

                    approval_id TEXT NOT NULL,

                    action_id TEXT NOT NULL,

                    execution_id TEXT,

                    status TEXT NOT NULL,

                    approved_by TEXT,

                    approved_at TEXT,

                    created_at TEXT NOT NULL

                )
                """
            )



    def create(
        self,
        approval_id: str,
        action_id: str,
    ):


        item = NotificationResponseApprovalBinding(

            binding_id=str(
                uuid4()
            ),

            approval_id=approval_id,

            action_id=action_id,

            execution_id=None,

            status=
                ApprovalExecutionStatus.WAITING,

            approved_by=None,

            approved_at=None,

            created_at=datetime.now(
                timezone.utc
            ),

        )



        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO
                notification_response_approval_binding
                (
                    binding_id,
                    approval_id,
                    action_id,
                    execution_id,
                    status,
                    approved_by,
                    approved_at,
                    created_at
                )

                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)

                """,

                (

                    item.binding_id,

                    item.approval_id,

                    item.action_id,

                    item.execution_id,

                    item.status.value,

                    item.approved_by,

                    None,

                    item.created_at.isoformat(),

                ),
            )


        return item



    def update_execution(
        self,
        binding_id: str,
        execution_id: str,
        status: ApprovalExecutionStatus,
    ):


        with self._connect() as connection:

            connection.execute(
                """
                UPDATE
                notification_response_approval_binding

                SET

                    execution_id = ?,

                    status = ?

                WHERE binding_id = ?

                """,

                (

                    execution_id,

                    status.value,

                    binding_id,

                ),
            )



    def latest(self):

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT

                    binding_id,

                    approval_id,

                    action_id,

                    execution_id,

                    status,

                    approved_by,

                    approved_at,

                    created_at


                FROM notification_response_approval_binding

                ORDER BY created_at DESC

                LIMIT 1

                """
            ).fetchone()



        if not row:

            return None



        return NotificationResponseApprovalBinding(

            binding_id=row[0],

            approval_id=row[1],

            action_id=row[2],

            execution_id=row[3],

            status=
                ApprovalExecutionStatus(row[4]),

            approved_by=row[5],

            approved_at=
                datetime.fromisoformat(row[6])
                if row[6]
                else None,

            created_at=
                datetime.fromisoformat(row[7]),

        )



    def list_history(
        self,
        limit:int = 50,
    ):


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT

                    binding_id,

                    approval_id,

                    action_id,

                    execution_id,

                    status,

                    approved_by,

                    approved_at,

                    created_at


                FROM notification_response_approval_binding

                ORDER BY created_at DESC

                LIMIT ?

                """,
                (
                    limit,
                ),
            ).fetchall()



        return [

            NotificationResponseApprovalBinding(

                binding_id=row[0],

                approval_id=row[1],

                action_id=row[2],

                execution_id=row[3],

                status=
                    ApprovalExecutionStatus(row[4]),

                approved_by=row[5],

                approved_at=
                    datetime.fromisoformat(row[6])
                    if row[6]
                    else None,

                created_at=
                    datetime.fromisoformat(row[7]),

            )

            for row in rows

        ]
