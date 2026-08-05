from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from app.models.notification_response_approval import (
    NotificationResponseApproval,
    ApprovalStatus,
)


class NotificationResponseApprovalStore:

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
            CREATE TABLE IF NOT EXISTS notification_response_approval (
                approval_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                requested_reason TEXT NOT NULL,
                status TEXT NOT NULL,
                approved_by TEXT,
                requested_at TEXT NOT NULL,
                approved_at TEXT
            )
            """)

    def create_request(self, execution_id: str, action_id: str, action_type: str, requested_reason: str):
        item = NotificationResponseApproval(
            approval_id=str(uuid4()),
            execution_id=execution_id,
            action_id=action_id,
            action_type=action_type,
            requested_reason=requested_reason,
            status=ApprovalStatus.PENDING,
            approved_by=None,
            requested_at=datetime.now(timezone.utc),
            approved_at=None,
        )
        with self._connect() as connection:
            connection.execute("""
            INSERT INTO notification_response_approval
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.approval_id,
                item.execution_id,
                item.action_id,
                item.action_type,
                item.requested_reason,
                item.status.value,
                item.approved_by,
                item.requested_at.isoformat(),
                None,
            ))
        return item

    def approve(self, approval_id: str, approved_by: str):
        return self._update_status(approval_id, ApprovalStatus.APPROVED, approved_by)

    def reject(self, approval_id: str, approved_by: str):
        return self._update_status(approval_id, ApprovalStatus.REJECTED, approved_by)

    def _update_status(self, approval_id, status, approved_by):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("""
            UPDATE notification_response_approval
            SET status=?, approved_by=?, approved_at=?
            WHERE approval_id=?
            """, (status.value, approved_by, now, approval_id))
        return self.get(approval_id)

    def get(self, approval_id: str):
        with self._connect() as connection:
            row = connection.execute("""
            SELECT * FROM notification_response_approval
            WHERE approval_id=?
            """, (approval_id,)).fetchone()
        return self._row_to_model(row)

    def pending(self, limit: int = 50):
        with self._connect() as connection:
            rows = connection.execute("""
            SELECT * FROM notification_response_approval
            WHERE status=?
            ORDER BY requested_at DESC
            LIMIT ?
            """, (ApprovalStatus.PENDING.value, limit)).fetchall()
        return [self._row_to_model(row) for row in rows]

    def list_history(self, limit: int = 100):
        with self._connect() as connection:
            rows = connection.execute("""
            SELECT * FROM notification_response_approval
            ORDER BY requested_at DESC
            LIMIT ?
            """, (limit,)).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def latest(self):
        with self._connect() as connection:
            row = connection.execute("""
            SELECT * FROM notification_response_approval
            ORDER BY requested_at DESC
            LIMIT 1
            """).fetchone()
        return self._row_to_model(row)

    def _row_to_model(self, row):
        if not row:
            return None
        return NotificationResponseApproval(
            approval_id=row[0],
            execution_id=row[1],
            action_id=row[2],
            action_type=row[3],
            requested_reason=row[4],
            status=ApprovalStatus(row[5]),
            approved_by=row[6],
            requested_at=datetime.fromisoformat(row[7]),
            approved_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    def _row_to_dict(self, row):
        return {
            "approval_id": row[0],
            "execution_id": row[1],
            "action_id": row[2],
            "action_type": row[3],
            "requested_reason": row[4],
            "status": row[5],
            "approved_by": row[6],
            "requested_at": row[7],
            "approved_at": row[8],
        }

