from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import (
    PlainTextResponse,
)

from app.api.v1.execution_runtime_observability import (
    get_runtime_observability_service,
)
from app.services.prometheus_runtime_metrics import (
    PROMETHEUS_CONTENT_TYPE,
    render_runtime_prometheus_metrics,
)


router = APIRouter(
    prefix="/execution-runtime-observability",
    tags=["execution-runtime-prometheus"],
)


@router.get(
    "/prometheus",
    response_class=PlainTextResponse,
)
async def execution_runtime_prometheus_metrics(
) -> PlainTextResponse:
    """
    Export live recovery-runtime observability using Prometheus text
    exposition format.

    The endpoint reads coordination state only. It does not start the
    runtime, persist a new snapshot, contact managed devices, or
    execute network commands.
    """

    try:
        service = (
            get_runtime_observability_service()
        )

        metrics = service.build_snapshot()

        current = service.get_current_metrics()

        metrics_version = (
            current[1]
            if current is not None
            else 0
        )

        content = (
            render_runtime_prometheus_metrics(
                metrics,
                metrics_version=
                    metrics_version,
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
