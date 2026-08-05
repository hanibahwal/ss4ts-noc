from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pathlib import Path
import sqlite3
import uuid
import os


# ==========================================================
# SS4TS Remediation Audit History Database
# H23.4.5.5.12.X.4.8
# Autonomous Remediation Audit Timeline
# ==========================================================


SS4TS_DATA_DIR = os.getenv(
    "SS4TS_DATA_DIR",
    "./data",
)


DB_PATH = Path(
    os.getenv(
        "SS4TS_REMEDIATION_AUDIT_DB",
        str(
            Path(SS4TS_DATA_DIR)
            / "remediation-audit.db"
        ),
    )
)


ENGINE_NAME = (
    "SS4TS Remediation Audit Timeline Engine"
)


ENGINE_VERSION = (
    "1.1.0-production-volume"
)


# ==========================================================
# Time Helper
# ==========================================================

def _now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==========================================================
# Database Initialization
# ==========================================================

def _init_db():

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS remediation_history
            (
                id TEXT PRIMARY KEY,
                router_ip TEXT,
                action_type TEXT,
                priority TEXT,
                approval_status TEXT,
                execution_status TEXT,
                verification_status TEXT,
                business_impact TEXT,
                confidence INTEGER,
                recommendation TEXT,
                created_at TEXT
            )
            """
        )

        conn.commit()


_init_db()


# ==========================================================
# Save Remediation History
# ==========================================================

def save_remediation_history(
    *,
    router_ip: str,
    action_type: str,
    priority: str,
    approval_status: str,
    execution_status: str,
    verification_status: str,
    business_impact: str,
    confidence: int,
    recommendation: str,
) -> str:


    record_id = str(
        uuid.uuid4()
    )


    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            INSERT INTO remediation_history
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record_id,
                router_ip,
                action_type,
                priority,
                approval_status,
                execution_status,
                verification_status,
                business_impact,
                confidence,
                recommendation,
                _now(),
            ),
        )


        conn.commit()


    return record_id


# ==========================================================
# Read Remediation History
# ==========================================================

def get_remediation_history() -> list[dict[str, Any]]:


    with sqlite3.connect(DB_PATH) as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM remediation_history
            ORDER BY created_at DESC
            """
        ).fetchall()


    return [

        {
            "id": row[0],
            "router_ip": row[1],
            "action_type": row[2],
            "priority": row[3],
            "approval_status": row[4],
            "execution_status": row[5],
            "verification_status": row[6],
            "business_impact": row[7],
            "confidence": row[8],
            "recommendation": row[9],
            "created_at": row[10],
        }

        for row in rows

    ]
