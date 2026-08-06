from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Address
import os
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from app.models.execution_intent import (
    ExecutionIntent,
)


ENGINE_NAME = (
    "SS4TS Human Approval Workflow Engine"
)

ENGINE_VERSION = (
    "3.0.0-immutable-execution-intent"
)

SS4TS_DATA_DIR = os.getenv(
    "SS4TS_DATA_DIR",
    "./data",
)

DB_PATH = (
    Path(SS4TS_DATA_DIR)
    / "remediation_approval.db"
)

INTENT_TTL_MINUTES = 30

READ_ONLY_ACTIONS = frozenset({
    "CHECK_CPU_PROCESS",
    "CHECK_FIREWALL_LOAD",
    "ANALYZE_TRAFFIC_LOAD",
})

COLUMNS = [
    "approval_id",
    "router_ip",
    "action_type",
    "reason",
    "priority",
    "status",
    "created_at",
    "approved_by",
    "approved_at",
    "rejected_by",
    "rejected_at",
    "intent_version",
    "execution_class",
    "read_only",
    "verification_required",
    "rollback_required",
    "expires_at",
    "intent_fingerprint",
]


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _expires_at(
    ttl_minutes: int,
) -> str:
    return (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=ttl_minutes
        )
    ).isoformat()


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return connection


def _row_to_dict(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    if row is None:
        return None

    payload = dict(row)

    for field_name in (
        "read_only",
        "verification_required",
        "rollback_required",
    ):
        if (
            field_name in payload
            and payload[field_name]
            is not None
        ):
            payload[field_name] = bool(
                payload[field_name]
            )

    return payload


def _column_names(
    connection: sqlite3.Connection,
) -> set[str]:
    rows = connection.execute(
        "PRAGMA table_info(approvals)"
    ).fetchall()

    return {
        str(row["name"])
        for row in rows
    }


def _init_db() -> None:
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS approvals
            (
                approval_id TEXT PRIMARY KEY,
                router_ip TEXT NOT NULL,
                action_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                rejected_by TEXT,
                rejected_at TEXT,
                intent_version TEXT,
                execution_class TEXT,
                read_only INTEGER,
                verification_required INTEGER,
                rollback_required INTEGER,
                expires_at TEXT,
                intent_fingerprint TEXT
            )
            """
        )

        columns = _column_names(
            connection
        )

        migrations = {
            "intent_version":
                "TEXT",
            "execution_class":
                "TEXT",
            "read_only":
                "INTEGER",
            "verification_required":
                "INTEGER",
            "rollback_required":
                "INTEGER",
            "expires_at":
                "TEXT",
            "intent_fingerprint":
                "TEXT",
        }

        for name, sql_type in (
            migrations.items()
        ):
            if name not in columns:
                connection.execute(
                    "ALTER TABLE approvals "
                    f"ADD COLUMN {name} "
                    f"{sql_type}"
                )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_approvals_status
            ON approvals(status)
            """
        )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_approvals_intent_fingerprint
            ON approvals(intent_fingerprint)
            WHERE intent_fingerprint IS NOT NULL
            """
        )

        connection.commit()


_init_db()


def _execution_profile(
    action_type: str,
) -> dict[str, Any]:
    read_only = (
        action_type
        in READ_ONLY_ACTIONS
    )

    return {
        "execution_class": (
            "READ_ONLY"
            if read_only
            else "MUTATING"
        ),
        "read_only":
            read_only,
        "verification_required":
            True,
        "rollback_required":
            not read_only,
    }


def _intent_from_approval(
    approval: dict[str, Any],
) -> ExecutionIntent:
    return ExecutionIntent(
        approval_id=str(
            approval["approval_id"]
        ),
        router_ip=str(
            approval["router_ip"]
        ),
        action_type=str(
            approval["action_type"]
        ),
        execution_class=str(
            approval["execution_class"]
        ),
        read_only=bool(
            approval["read_only"]
        ),
        verification_required=bool(
            approval[
                "verification_required"
            ]
        ),
        rollback_required=bool(
            approval[
                "rollback_required"
            ]
        ),
        expires_at=str(
            approval["expires_at"]
        ),
        intent_version=str(
            approval["intent_version"]
        ),
    )


def create_approval_request(
    *,
    router_ip: str,
    action_type: str,
    reason: str,
    priority: str = "HIGH",
    intent_ttl_minutes: int = (
        INTENT_TTL_MINUTES
    ),
) -> dict[str, Any]:
    normalized_router_ip = str(
        IPv4Address(
            str(router_ip).strip()
        )
    )

    normalized_action = str(
        action_type
    ).strip()

    normalized_reason = str(
        reason
    ).strip()

    normalized_priority = str(
        priority
    ).strip().upper()

    if not normalized_action:
        raise ValueError(
            "action_type is required"
        )

    if not normalized_reason:
        raise ValueError(
            "reason is required"
        )

    if intent_ttl_minutes <= 0:
        raise ValueError(
            "intent_ttl_minutes must be positive"
        )

    with _connect() as connection:
        existing = connection.execute(
            """
            SELECT *
            FROM approvals
            WHERE router_ip=?
              AND action_type=?
              AND status='WAITING_APPROVAL'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                normalized_router_ip,
                normalized_action,
            ),
        ).fetchone()

        if existing is not None:
            approval = _row_to_dict(
                existing
            )

            return {
                "engine": {
                    "name": ENGINE_NAME,
                    "version": ENGINE_VERSION,
                },
                "approval": approval,
                "duplicate": True,
                "intent": (
                    _intent_from_approval(
                        approval
                    ).to_dict()
                    if approval.get(
                        "intent_fingerprint"
                    )
                    else None
                ),
            }

        approval_id = str(
            uuid.uuid4()
        )

        profile = _execution_profile(
            normalized_action
        )

        intent = ExecutionIntent(
            approval_id=approval_id,
            router_ip=normalized_router_ip,
            action_type=normalized_action,
            execution_class=profile[
                "execution_class"
            ],
            read_only=profile[
                "read_only"
            ],
            verification_required=profile[
                "verification_required"
            ],
            rollback_required=profile[
                "rollback_required"
            ],
            expires_at=_expires_at(
                intent_ttl_minutes
            ),
        )

        created_at = _now()

        connection.execute(
            """
            INSERT INTO approvals
            (
                approval_id,
                router_ip,
                action_type,
                reason,
                priority,
                status,
                created_at,
                intent_version,
                execution_class,
                read_only,
                verification_required,
                rollback_required,
                expires_at,
                intent_fingerprint
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_id,
                normalized_router_ip,
                normalized_action,
                normalized_reason,
                normalized_priority,
                "WAITING_APPROVAL",
                created_at,
                intent.intent_version,
                intent.execution_class,
                int(intent.read_only),
                int(
                    intent.verification_required
                ),
                int(
                    intent.rollback_required
                ),
                intent.expires_at,
                intent.fingerprint,
            ),
        )

        connection.commit()

    approval = get_approval_by_id(
        approval_id
    )

    return {
        "engine": {
            "name": ENGINE_NAME,
            "version": ENGINE_VERSION,
        },
        "approval": approval,
        "duplicate": False,
        "intent": intent.to_dict(),
    }


def get_pending_approvals(
) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM approvals
            WHERE status='WAITING_APPROVAL'
            ORDER BY created_at
            """
        ).fetchall()

    return [
        item
        for row in rows
        if (
            item := _row_to_dict(
                row
            )
        ) is not None
    ]


def get_approval_by_id(
    approval_id: str,
) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM approvals
            WHERE approval_id=?
            """,
            (
                str(
                    approval_id
                ).strip(),
            ),
        ).fetchone()

    return _row_to_dict(
        row
    )


def get_execution_intent(
    approval_id: str,
) -> ExecutionIntent | None:
    approval = get_approval_by_id(
        approval_id
    )

    if (
        approval is None
        or not approval.get(
            "intent_fingerprint"
        )
    ):
        return None

    return _intent_from_approval(
        approval
    )


def validate_execution_intent(
    approval_id: str,
) -> dict[str, Any]:
    approval = get_approval_by_id(
        approval_id
    )

    if approval is None:
        return {
            "valid": False,
            "reason":
                "Approval request not found",
            "approval": None,
            "intent": None,
        }

    intent = get_execution_intent(
        approval_id
    )

    if intent is None:
        return {
            "valid": False,
            "reason":
                "Approval has no immutable intent",
            "approval": approval,
            "intent": None,
        }

    stored_fingerprint = str(
        approval.get(
            "intent_fingerprint",
            "",
        )
    )

    if not intent.verify_fingerprint(
        stored_fingerprint
    ):
        return {
            "valid": False,
            "reason":
                "Execution intent fingerprint mismatch",
            "approval": approval,
            "intent": intent.to_dict(),
        }

    if intent.expired:
        return {
            "valid": False,
            "reason":
                "Execution intent has expired",
            "approval": approval,
            "intent": intent.to_dict(),
        }

    return {
        "valid": True,
        "reason":
            "Execution intent verified",
        "approval": approval,
        "intent": intent.to_dict(),
    }


def approve_request(
    approval_id: str,
    approved_by: str = "NOC_OPERATOR",
) -> dict[str, Any]:
    validation = validate_execution_intent(
        approval_id
    )

    if not validation["valid"]:
        return {
            "success": False,
            "message":
                validation["reason"],
            "approval":
                validation["approval"],
        }

    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE approvals
            SET status='APPROVED',
                approved_by=?,
                approved_at=?
            WHERE approval_id=?
              AND status='WAITING_APPROVAL'
            """,
            (
                str(
                    approved_by
                ).strip(),
                _now(),
                approval_id,
            ),
        )

        connection.commit()

    if cursor.rowcount != 1:
        return {
            "success": False,
            "message":
                "Approval is not waiting for approval",
            "approval":
                get_approval_by_id(
                    approval_id
                ),
        }

    return {
        "success": True,
        "approval":
            get_approval_by_id(
                approval_id
            ),
    }


def approve_remediation(
    approval_id: str,
    approved_by: str = "NOC_OPERATOR",
) -> dict[str, Any]:
    return approve_request(
        approval_id=approval_id,
        approved_by=approved_by,
    )


def reject_remediation(
    approval_id: str,
    rejected_by: str = "NOC_OPERATOR",
) -> dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE approvals
            SET status='REJECTED',
                rejected_by=?,
                rejected_at=?
            WHERE approval_id=?
              AND status='WAITING_APPROVAL'
            """,
            (
                str(
                    rejected_by
                ).strip(),
                _now(),
                approval_id,
            ),
        )

        connection.commit()

    if cursor.rowcount != 1:
        return {
            "success": False,
            "message":
                "Approval cannot be rejected",
            "approval":
                get_approval_by_id(
                    approval_id
                ),
        }

    return {
        "success": True,
        "approval":
            get_approval_by_id(
                approval_id
            ),
    }


def claim_approval_for_execution(
    approval_id: str,
) -> dict[str, Any]:
    normalized_id = str(
        approval_id
    ).strip()

    validation = (
        validate_execution_intent(
            normalized_id
        )
    )

    if not validation["valid"]:
        return {
            "claimed": False,
            "reason":
                validation["reason"],
            "approval":
                validation["approval"],
            "intent":
                validation["intent"],
        }

    with _connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = connection.execute(
            """
            UPDATE approvals
            SET status='EXECUTING'
            WHERE approval_id=?
              AND status='APPROVED'
              AND intent_fingerprint=?
            """,
            (
                normalized_id,
                validation["intent"][
                    "intent_fingerprint"
                ],
            ),
        )

        if cursor.rowcount != 1:
            connection.rollback()

            return {
                "claimed": False,
                "reason":
                    "Approval is not executable or was already consumed",
                "approval":
                    get_approval_by_id(
                        normalized_id
                    ),
                "intent":
                    validation["intent"],
            }

        connection.commit()

    return {
        "claimed": True,
        "reason": "Approval claimed",
        "approval":
            get_approval_by_id(
                normalized_id
            ),
        "intent":
            validation["intent"],
    }


def finalize_approval_execution(
    approval_id: str,
    *,
    succeeded: bool,
) -> dict[str, Any] | None:
    final_status = (
        "EXECUTED"
        if succeeded
        else "EXECUTION_FAILED"
    )

    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE approvals
            SET status=?
            WHERE approval_id=?
              AND status='EXECUTING'
            """,
            (
                final_status,
                approval_id,
            ),
        )

        connection.commit()

    if cursor.rowcount != 1:
        return None

    return get_approval_by_id(
        approval_id
    )


def get_executing_approvals(
) -> list[dict[str, Any]]:
    """
    Return approvals left in EXECUTING state.

    Used only by controlled-execution recovery reconciliation.
    """
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM approvals
            WHERE status='EXECUTING'
            ORDER BY created_at
            """
        ).fetchall()

    return [
        item
        for row in rows
        if (
            item := _row_to_dict(
                row
            )
        ) is not None
    ]


def recover_executing_approval_as_failed(
    approval_id: str,
) -> dict[str, Any] | None:
    """
    Atomically recover an orphan EXECUTING approval.

    EXECUTING -> EXECUTION_FAILED
    """
    normalized_id = str(
        approval_id
    ).strip()

    if not normalized_id:
        return None

    with _connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = connection.execute(
            """
            UPDATE approvals
            SET status='EXECUTION_FAILED'
            WHERE approval_id=?
              AND status='EXECUTING'
            """,
            (
                normalized_id,
            ),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return None

        connection.commit()

    return get_approval_by_id(
        normalized_id
    )


def get_executing_approvals(
) -> list[dict[str, Any]]:
    """
    Return approvals left in EXECUTING state.

    Used only by controlled-execution recovery reconciliation.
    """
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM approvals
            WHERE status='EXECUTING'
            ORDER BY created_at
            """
        ).fetchall()

    return [
        item
        for row in rows
        if (
            item := _row_to_dict(
                row
            )
        ) is not None
    ]


def recover_executing_approval_as_failed(
    approval_id: str,
) -> dict[str, Any] | None:
    """
    Atomically recover an orphan EXECUTING approval.

    EXECUTING -> EXECUTION_FAILED
    """
    normalized_id = str(
        approval_id
    ).strip()

    if not normalized_id:
        return None

    with _connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = connection.execute(
            """
            UPDATE approvals
            SET status='EXECUTION_FAILED'
            WHERE approval_id=?
              AND status='EXECUTING'
            """,
            (
                normalized_id,
            ),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return None

        connection.commit()

    return get_approval_by_id(
        normalized_id
    )
