from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.services.shadow_decision_store import (
    DEFAULT_SHADOW_DATABASE,
    ShadowDecisionStore,
)
from app.api.v1.decision_audits import (
    get_audit_store,
)
from app.services.outcome_comparison import (
    compare_shadow_to_evidence,
)


router = APIRouter(
    prefix="/autonomous-shadow",
    tags=["Autonomous Shadow Mode"],
)


def get_shadow_database_path() -> Path:
    configured = os.getenv(
        "SS4TS_SHADOW_DECISION_DB",
        str(DEFAULT_SHADOW_DATABASE),
    ).strip()

    if not configured:
        raise RuntimeError(
            "SS4TS_SHADOW_DECISION_DB "
            "must not be empty"
        )

    return Path(configured)


def get_shadow_store() -> ShadowDecisionStore:
    return ShadowDecisionStore(
        get_shadow_database_path()
    )


def _summary(record) -> dict:
    return {
        "shadow_id": record.shadow_id,
        "decision_id": record.decision_id,
        "source_node_id": record.source_node_id,
        "proposed_action": record.proposed_action,
        "confidence_percent":
            record.confidence_percent,
        "risk_level": record.risk_level,
        "simulation_status":
            record.simulation_status,
        "dry_run_only": record.dry_run_only,
        "created_at":
            record.created_at.isoformat(),
        "predicted_outcome":
            dict(record.predicted_outcome),
        "safety": {
            "shadow_mode": True,
            "read_only": True,
            "execution_enabled": False,
            "execution_authority": False,
            "network_io_performed": False,
            "device_command_executed": False,
        },
    }


@router.get("")
async def list_shadow_decisions(
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=1000,
        ),
    ] = 100,
) -> dict:
    try:
        store = get_shadow_store()
        records = store.list_recent(
            limit=limit
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
        "limit": limit,
        "records": [
            _summary(record)
            for record in records
        ],
        "safety": {
            "read_only": True,
            "execution_enabled": False,
            "execution_authority": False,
            "network_io_performed": False,
            "device_command_executed": False,
        },
    }


@router.get(
    "/{shadow_id}/outcome-comparison"
)
async def get_shadow_outcome_comparison(
    shadow_id: str,
) -> dict:
    """
    Compare one shadow prediction with the newest
    verified execution-evidence snapshot for the
    same decision.

    Read-only local persistence access only.
    """
    try:
        shadow_store = get_shadow_store()

        shadow = shadow_store.get(
            shadow_id
        )

        if shadow is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Shadow decision not found: "
                    f"{shadow_id}"
                ),
            )

        audit_store = get_audit_store()

        candidates = (
            audit_store.list_records(
                decision_id=
                    shadow.decision_id,
                limit=100,
                offset=0,
            )
        )

        evidence = None

        for candidate in candidates:
            if not candidate.metadata.get(
                "evidence_bundle",
                False,
            ):
                continue

            if not audit_store.verify(
                candidate.audit_id
            ):
                continue

            evidence = candidate
            break

        if evidence is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Verified execution evidence "
                    "not found for decision: "
                    f"{shadow.decision_id}"
                ),
            )

        comparison = (
            compare_shadow_to_evidence(
                shadow=shadow,
                audit=evidence,
            )
        )

    except HTTPException:
        raise
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    response = comparison.to_dict()

    response["evidence_verified"] = True

    return response


@router.get("/{shadow_id}")
async def get_shadow_decision(
    shadow_id: str,
) -> dict:
    try:
        store = get_shadow_store()
        record = store.get(shadow_id)
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
                "Shadow decision not found: "
                f"{shadow_id}"
            ),
        )

    response = record.to_dict()

    response["safety"] = {
        "shadow_mode": True,
        "read_only": True,
        "execution_enabled": False,
        "execution_authority": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }

    return response
