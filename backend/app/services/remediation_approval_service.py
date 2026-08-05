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


DB_PATH = Path(
    "/app/data/approval_workflow.db"
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
