from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.api.v1.knowledge_graph import (
    build_runtime_graph,
)
from app.services.decision_audit_store import (
    DEFAULT_AUDIT_DATABASE,
    DecisionAuditStore,
)
from app.services.decision_explanation import (
    build_decision_explanation,
)
from app.services.decision_trace import (
    build_decision_trace,
)
from app.services.execution_planner import (
    build_execution_plan,
)


router = APIRouter(
    tags=["decision-audits"],
)


def get_audit_database_path() -> Path:
    configured = os.getenv(
        "SS4TS_DECISION_AUDIT_DB",
        str(DEFAULT_AUDIT_DATABASE),
    ).strip()

    if not configured:
        raise RuntimeError(
            "SS4TS_DECISION_AUDIT_DB "
            "must not be empty"
        )

    return Path(configured)


def get_audit_store() -> DecisionAuditStore:
    return DecisionAuditStore(
        get_audit_database_path()
    )


def _record_summary(
    record,
) -> dict:
    return {
        "audit_id":
            record.audit_id,
        "trace_id":
            record.trace_id,
        "decision_id":
            record.decision_id,
        "source_node_id":
            record.source_node_id,
        "created_at":
            record.created_at.isoformat(),
        "status":
            record.status.value,
        "risk_level":
            record.risk_level,
        "risk_score":
            record.risk_score,
        "primary_cause_id":
            record.primary_cause_id,
        "checksum":
            record.checksum,
        "content": {
            "has_explanation":
                record.has_explanation,
            "has_execution_plan":
                record.has_execution_plan,
            "has_simulation":
                record.has_simulation,
        },
    }


@router.post(
    "/knowledge-graph/nodes/{node_id}/"
    "decision/audit"
)
async def create_decision_audit(
    node_id: str,
    max_depth: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 10,
    refresh: bool = False,
) -> dict:
    """
    Generate and persist a read-only decision audit snapshot.

    No command is executed against a managed network device.
    """

    graph = await build_runtime_graph(
        refresh=refresh
    )

    try:
        trace = build_decision_trace(
            graph,
            node_id,
            max_depth=max_depth,
        )

        explanation = (
            build_decision_explanation(
                graph,
                node_id,
                max_depth=max_depth,
            )
        )

        execution_plan = (
            build_execution_plan(
                graph,
                node_id,
                max_depth=max_depth,
            )
        )

        store = get_audit_store()

        record = store.create_record(
            trace=trace,
            explanation=explanation,
            execution_plan=
                execution_plan,
            metadata={
                "created_by":
                    "decision-audit-api",
                "max_depth":
                    max_depth,
                "refresh":
                    refresh,
            },
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Graph node not found: "
                f"{node_id}"
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    response = record.to_dict()

    response["verified"] = (
        store.verify(
            record.audit_id
        )
    )

    response["safety"] = {
        "read_only_snapshot":
            True,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return response


@router.get(
    "/decision-audits"
)
async def list_decision_audits(
    source_node_id: str | None = None,
    decision_id: str | None = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=1000,
        ),
    ] = 100,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> dict:
    try:
        store = get_audit_store()

        records = store.list_records(
            source_node_id=
                source_node_id,
            decision_id=decision_id,
            limit=limit,
            offset=offset,
        )

        total = store.count(
            source_node_id=
                source_node_id,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return {
        "count": len(records),
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": [
            _record_summary(
                record
            )
            for record in records
        ],
    }


@router.get(
    "/decision-audits/{audit_id}"
)
async def get_decision_audit(
    audit_id: str,
) -> dict:
    try:
        store = get_audit_store()
        record = store.get(
            audit_id
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Decision audit not found: "
                f"{audit_id}"
            ),
        )

    response = record.to_dict()

    response["verified"] = (
        store.verify(
            record.audit_id
        )
    )

    return response


@router.get(
    "/decision-audits/{audit_id}/verify"
)
async def verify_decision_audit(
    audit_id: str,
) -> dict:
    try:
        store = get_audit_store()
        record = store.get(
            audit_id
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Decision audit not found: "
                f"{audit_id}"
            ),
        )

    verified = store.verify(
        audit_id
    )

    return {
        "audit_id":
            audit_id,
        "checksum":
            record.checksum,
        "verified":
            verified,
        "integrity_status": (
            "valid"
            if verified
            else "corrupted"
        ),
        "checksum_algorithm":
            "sha256",
    }
