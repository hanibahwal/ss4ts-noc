from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Row, connect
from uuid import uuid4

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditRecord,
    NotificationAuditResult,
)

from app.models.notification_audit_query import (
    NotificationAuditQuery,
)


class NotificationAuditStoreError(
    Exception
):
    pass


@dataclass
class NotificationAuditStore:

    database: Path


    def __post_init__(self) -> None:

        self._initialize()



    def _connect(self):

        connection = connect(
            self.database
        )

        connection.row_factory = Row

        return connection



    def _initialize(self) -> None:

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



    def _row_to_record(
        self,
        row: Row,
    ) -> NotificationAuditRecord:

        return NotificationAuditRecord(

            audit_id=row["audit_id"],

            identity_id=row["identity_id"],

            action=NotificationAuditAction(
                row["action"]
            ),

            result=NotificationAuditResult(
                row["result"]
            ),

            resource=row["resource"],

            resource_id=row["resource_id"],

            message=row["message"],

            created_at=None,
        )



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

            self._row_to_record(row)

            for row in rows

        ]



    def query_audits(
        self,
        query: NotificationAuditQuery,
    ) -> list[NotificationAuditRecord]:


        sql = """
            SELECT *
            FROM notification_audit
        """


        conditions = []

        params = []


        if query.identity_id:

            conditions.append(
                "identity_id = ?"
            )

            params.append(
                query.identity_id
            )


        if query.action:

            conditions.append(
                "action = ?"
            )

            params.append(
                query.action.value
            )


        if query.result:

            conditions.append(
                "result = ?"
            )

            params.append(
                query.result.value
            )


        if query.resource:

            conditions.append(
                "resource = ?"
            )

            params.append(
                query.resource
            )


        if query.resource_id:

            conditions.append(
                "resource_id = ?"
            )

            params.append(
                query.resource_id
            )


        if query.from_date:

            conditions.append(
                "created_at >= ?"
            )

            params.append(
                query.from_date.isoformat()
            )


        if query.to_date:

            conditions.append(
                "created_at <= ?"
            )

            params.append(
                query.to_date.isoformat()
            )


        if conditions:

            sql += (
                " WHERE "
                + " AND ".join(
                    conditions
                )
            )


        sql += """
            ORDER BY created_at DESC

            LIMIT ?

            OFFSET ?
        """


        params.extend(
            [
                query.limit,
                query.offset,
            ]
        )


        with closing(
            self._connect()
        ) as connection:

            rows = connection.execute(
                sql,
                params,
            ).fetchall()


        return [

            self._row_to_record(row)

            for row in rows

        ]



    def count_audits(
        self,
        query: NotificationAuditQuery,
    ) -> int:


        results = self.query_audits(
            NotificationAuditQuery(
                identity_id=query.identity_id,
                action=query.action,
                result=query.result,
                resource=query.resource,
                resource_id=query.resource_id,
                from_date=query.from_date,
                to_date=query.to_date,
                limit=1000000,
                offset=0,
            )
        )


        return len(results)



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



        return self._row_to_record(
            row
        )
