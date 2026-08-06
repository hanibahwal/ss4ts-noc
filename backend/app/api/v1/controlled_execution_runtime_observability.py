from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import (
    PlainTextResponse,
)

from app.services.controlled_execution_runtime_observability import (
    get_controlled_runtime_observability as get_controlled_runtime_observability_service,
)
from app.services.controlled_execution_runtime_prometheus import (
    PROMETHEUS_CONTENT_TYPE,
    render_controlled_runtime_prometheus,
)


router = APIRouter(
    prefix=(
        "/remediation/"
        "controlled-recovery-runtime/"
        "observability"
    ),
    tags=[
        "controlled-execution-runtime-observability"
    ],
)


@router.get("")
async def get_controlled_runtime_observability(
) -> dict:
    try:
        service = (
            get_controlled_runtime_observability_service()
        )

        return service.build_snapshot()

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


@router.get(
    "/health",
)
async def get_controlled_runtime_health(
) -> dict:
    try:
        snapshot = (
            get_controlled_runtime_observability_service()
            .build_snapshot()
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

    runtime = snapshot["runtime"]

    return {
        "health_status":
            runtime["health_status"],
        "environment_enabled":
            runtime["environment_enabled"],
        "running":
            runtime["running"],
        "last_error":
            runtime["last_error"],
        "last_cycle_age_seconds":
            runtime[
                "last_cycle_age_seconds"
            ],
        "safety":
            snapshot["safety"],
        "collected_at":
            snapshot["collected_at"],
    }


@router.get(
    "/prometheus",
    response_class=PlainTextResponse,
)
async def get_controlled_runtime_prometheus(
) -> PlainTextResponse:
    try:
        snapshot = (
            get_controlled_runtime_observability_service()
            .build_snapshot()
        )

        content = (
            render_controlled_runtime_prometheus(
                snapshot
            )
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

    return PlainTextResponse(
        content=content,
        media_type=PROMETHEUS_CONTENT_TYPE,
    )
