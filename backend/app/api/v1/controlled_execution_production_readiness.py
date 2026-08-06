from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.services.controlled_execution_production_readiness import (
    evaluate_controlled_execution_readiness,
)


router = APIRouter(
    prefix=(
        "/remediation/"
        "controlled-execution/"
        "readiness"
    ),
    tags=[
        "controlled-execution-readiness"
    ],
)


@router.get("")
async def controlled_execution_readiness(
) -> dict:
    """
    Return controlled-execution production-readiness evidence.

    This endpoint does not start the runtime, claim approvals,
    execute remediation, contact devices, or expose credentials.
    """
    try:
        return (
            evaluate_controlled_execution_readiness()
        )

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
