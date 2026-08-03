from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from sqlite3 import connect
from contextlib import closing
from uuid import uuid4

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditRecord,
    NotificationAuditResult,
)


class NotificationAuditStoreError(
    Exception
):
    pass


@dataclass
class NotificationAuditStore:

    database: Path


    def __post_init__(self):

        self._initialize()


    def _connect(self):

        return connect(
            self.database
        )


    def _initialize(self):

        with closing(
            self._connect()
        ) as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                notification_audit (
                    audit_id TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    resource_id TEXT,
                    message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.commit()


    def create_audit(
        self,
        *,
        identity_id: str,
        action: NotificationAuditAction,
        result: NotificationAuditResult,
        resource: str,
        resource_id: str | None = None,
        message: str = "",
    ) -> NotificationAuditRecord:


        record = NotificationAuditRecord(

            audit_id=f"audit:{uuid4()}",

            identity_id=identity_id,

            action=action,

            result=result,

            resource=resource,

            resource_id=resource_id,

            message=message,
        )


        with closing(
            self._connect()
        ) as connection:

            connection.execute(
                """
                INSERT INTO notification_audit
                (
                    audit_id,
                    identity_id,
                    action,
                    result,
                    resource,
                    resource_id,
                    message,
                    created_at
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.audit_id,
                    record.identity_id,
                    record.action.value,
                    record.result.value,
                    record.resource,
                    record.resource_id,
                    record.message,
                    record.created_at.isoformat(),
                ),
            )

            connection.commit()


        return record


    def list_audits(
        self,
    ) -> list[NotificationAuditRecord]:

        with closing(
            self._connect()
        ) as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM notification_audit
                ORDER BY created_at DESC
                """
            ).fetchall()


        return [
            NotificationAuditRecord(
                audit_id=row[0],
                identity_id=row[1],
                action=NotificationAuditAction(row[2]),
                result=NotificationAuditResult(row[3]),
                resource=row[4],
                resource_id=row[5],
                message=row[6],
            )
            for row in rows
        ]


    def get_audit(
        self,
        audit_id: str,
    ) -> NotificationAuditRecord | None:


        with closing(
            self._connect()
        ) as connection:

            row = connection.execute(
                """
                SELECT *
                FROM notification_audit
                WHERE audit_id = ?
                """,
                (
                    audit_id,
                ),
            ).fetchone()


        if row is None:
            return None


        return NotificationAuditRecord(
            audit_id=row[0],
            identity_id=row[1],
            action=NotificationAuditAction(row[2]),
            result=NotificationAuditResult(row[3]),
            resource=row[4],
            resource_id=row[5],
            message=row[6],
        )
