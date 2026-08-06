from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import sqlite3
import uuid
from pathlib import Path


ENGINE_NAME = (
    "SS4TS Human Approval Workflow Engine"
)


ENGINE_VERSION = (
    "2.1.0-persistent-production"
)


import os
from pathlib import Path


SS4TS_DATA_DIR = os.getenv(
    "SS4TS_DATA_DIR",
    "./data",
)


DB_PATH = (
    Path(SS4TS_DATA_DIR)
    / "remediation_approval.db"
)


DB_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)



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

]



def _now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()



def _row_to_dict(row):

    if not row:
        return None


    return dict(
        zip(
            COLUMNS,
            row,
        )
    )



def _init_db():

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
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

                rejected_at TEXT

            )
            """
        )


        conn.commit()



_init_db()





def create_approval_request(
    *,
    router_ip: str,
    action_type: str,
    reason: str,
    priority: str = "HIGH",
) -> dict[str, Any]:


    with sqlite3.connect(DB_PATH) as conn:


        existing = conn.execute(
            """
            SELECT *
            FROM approvals

            WHERE router_ip=?

            AND action_type=?

            AND status='WAITING_APPROVAL'

            """,
            (
                router_ip,
                action_type,
            ),
        ).fetchone()



        if existing:


            return {

                "engine": {

                    "name":
                        ENGINE_NAME,

                    "version":
                        ENGINE_VERSION,

                },


                "approval":
                    _row_to_dict(
                        existing
                    ),


                "duplicate":
                    True,

            }





        approval_id = str(
            uuid.uuid4()
        )



        created_at = _now()



        conn.execute(
            """
            INSERT INTO approvals
            (

                approval_id,

                router_ip,

                action_type,

                reason,

                priority,

                status,

                created_at

            )

            VALUES
            (?,?,?,?,?,?,?)

            """,
            (

                approval_id,

                router_ip,

                action_type,

                reason,

                priority,

                "WAITING_APPROVAL",

                created_at,

            ),
        )


        conn.commit()



    return {


        "engine": {

            "name":
                ENGINE_NAME,

            "version":
                ENGINE_VERSION,

        },


        "approval": {

            "approval_id":
                approval_id,

            "router_ip":
                router_ip,

            "action_type":
                action_type,

            "reason":
                reason,

            "priority":
                priority,

            "status":
                "WAITING_APPROVAL",

            "created_at":
                created_at,

        },


        "duplicate":
            False,

    }







def get_pending_approvals() -> list[dict[str, Any]]:


    with sqlite3.connect(DB_PATH) as conn:


        rows = conn.execute(
            """
            SELECT *

            FROM approvals

            WHERE status='WAITING_APPROVAL'

            ORDER BY created_at

            """
        ).fetchall()



    return [

        _row_to_dict(row)

        for row in rows

    ]







def get_approval_by_id(
    approval_id: str,
) -> dict[str, Any] | None:


    with sqlite3.connect(DB_PATH) as conn:


        row = conn.execute(
            """
            SELECT *

            FROM approvals

            WHERE approval_id=?

            """,
            (
                approval_id,
            ),
        ).fetchone()



    return _row_to_dict(
        row
    )







def approve_request(
    approval_id: str,
    approved_by: str = "NOC_OPERATOR",
):


    existing = get_approval_by_id(
        approval_id
    )



    if not existing:


        return {

            "success":
                False,


            "message":
                "Approval request not found",

        }




    with sqlite3.connect(DB_PATH) as conn:


        conn.execute(
            """
            UPDATE approvals

            SET

            status='APPROVED',

            approved_by=?,

            approved_at=?

            WHERE approval_id=?

            """,
            (

                approved_by,

                _now(),

                approval_id,

            ),
        )


        conn.commit()



    return get_approval_by_id(
        approval_id
    )







#
# Compatibility wrapper
# Used by old remediation_execution API
#

def approve_remediation(
    approval_id: str,
    approved_by: str = "NOC_OPERATOR",
):


    return approve_request(
        approval_id=approval_id,

        approved_by=approved_by,

    )







def reject_remediation(
    approval_id: str,
    rejected_by: str = "NOC_OPERATOR",
):


    existing = get_approval_by_id(
        approval_id
    )



    if not existing:


        return {

            "success":
                False,


            "message":
                "Approval request not found",

        }




    with sqlite3.connect(DB_PATH) as conn:


        conn.execute(
            """
            UPDATE approvals

            SET

            status='REJECTED',

            rejected_by=?,

            rejected_at=?

            WHERE approval_id=?

            """,
            (

                rejected_by,

                _now(),

                approval_id,

            ),
        )


        conn.commit()



    return get_approval_by_id(
        approval_id
    )


def approve_remediation(
    approval_id: str,
    approved_by: str = "NOC_OPERATOR",
) -> dict[str, Any]:

    approval = approve_request(
        approval_id=approval_id,
        approved_by=approved_by,
    )

    if not approval:
        return {
            "success": False,
            "message": "Approval request not found",
        }

    return {
        "success": True,
        "approval": approval,
    }


def claim_approval_for_execution(
    approval_id: str,
) -> dict[str, Any]:
    """
    Atomically claim an approved remediation for one execution only.

    APPROVED -> EXECUTING

    The conditional update prevents two workers from consuming the same
    approval concurrently.
    """
    normalized_id = str(
        approval_id
    ).strip()

    if not normalized_id:
        return {
            "claimed": False,
            "reason": "approval_id is required",
            "approval": None,
        }

    with sqlite3.connect(
        DB_PATH,
        timeout=30,
    ) as conn:
        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        row = conn.execute(
            """
            SELECT *
            FROM approvals
            WHERE approval_id=?
            """,
            (
                normalized_id,
            ),
        ).fetchone()

        if row is None:
            conn.rollback()

            return {
                "claimed": False,
                "reason":
                    "Approval request not found",
                "approval": None,
            }

        approval = _row_to_dict(
            row
        )

        if approval.get("status") != "APPROVED":
            conn.rollback()

            return {
                "claimed": False,
                "reason":
                    "Approval is not executable",
                "approval": approval,
            }

        cursor = conn.execute(
            """
            UPDATE approvals
            SET status='EXECUTING'
            WHERE approval_id=?
              AND status='APPROVED'
            """,
            (
                normalized_id,
            ),
        )

        if cursor.rowcount != 1:
            conn.rollback()

            return {
                "claimed": False,
                "reason":
                    "Approval was already consumed",
                "approval": approval,
            }

        conn.commit()

    claimed = get_approval_by_id(
        normalized_id
    )

    return {
        "claimed": True,
        "reason": "Approval claimed",
        "approval": claimed,
    }


def finalize_approval_execution(
    approval_id: str,
    *,
    succeeded: bool,
) -> dict[str, Any] | None:
    """
    Finalize an approval that is currently EXECUTING.
    """
    final_status = (
        "EXECUTED"
        if succeeded
        else "EXECUTION_FAILED"
    )

    with sqlite3.connect(
        DB_PATH,
        timeout=30,
    ) as conn:
        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )

        cursor = conn.execute(
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

        conn.commit()

    if cursor.rowcount != 1:
        return None

    return get_approval_by_id(
        approval_id
    )
