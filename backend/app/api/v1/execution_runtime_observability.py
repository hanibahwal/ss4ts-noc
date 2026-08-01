from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.api.v1.execution_authorizations import (
    get_authorization_database_path,
)
from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_heartbeat_store import (
    ExecutionHeartbeatStore,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from app.services.execution_recovery import (
    ExecutionRecoveryService,
)
from app.services.execution_recovery_scheduler_runtime import (
    get_recovery_scheduler_runtime,
)
from app.services.execution_recovery_scheduler_store import (
    ExecutionRecoverySchedulerStore,
)
from app.services.execution_runtime_metrics_store import (
    ExecutionRuntimeMetricsStore,
)
from app.services.execution_runtime_observability import (
    ExecutionRuntimeObservabilityService,
)


router = APIRouter(
    prefix="/execution-runtime-observability",
    tags=["execution-runtime-observability"],
)


def get_runtime_observability_service(
) -> ExecutionRuntimeObservabilityService:
    database_path = (
        get_authorization_database_path()
    )

    ExecutionAuthorizationStore(
        database_path
    )

    ExecutionLeaseStore(
        database_path
    )

    ExecutionHeartbeatStore(
        database_path
    )

    ExecutionRecoveryService(
        database_path
    )

    scheduler_store = (
        ExecutionRecoverySchedulerStore(
            database_path
        )
    )

    metrics_store = (
        ExecutionRuntimeMetricsStore(
            database_path
        )
    )

    runtime = get_recovery_scheduler_runtime(
        database_path
    )

    return ExecutionRuntimeObservabilityService(
        database_path,
        runtime=runtime,
        scheduler_store=scheduler_store,
        metrics_store=metrics_store,
    )


def _metrics_response(
    metrics: RecoveryRuntimeObservability,
    *,
    metrics_version: int | None = None,
    persisted: bool = False,
) -> dict:
    payload = metrics.to_dict()

    payload["metrics_version"] = (
        metrics_version
    )

    payload["persisted"] = bool(
        persisted
    )

    payload["safety"] = {
        "runtime_control_only":
            True,
        "observability_only":
            True,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return payload


@router.get("")
async def get_live_runtime_observability(
) -> dict:
    """
    Return a live observability snapshot without persisting it.
    """

    try:
        service = (
            get_runtime_observability_service()
        )

        metrics = service.build_snapshot()
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _metrics_response(
        metrics,
        persisted=False,
    )


@router.post("/collect")
async def collect_runtime_observability(
) -> dict:
    """
    Build and persist a new runtime metrics snapshot.
    """

    try:
        service = (
            get_runtime_observability_service()
        )

        metrics, version = (
            service.collect_and_persist()
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

    return _metrics_response(
        metrics,
        metrics_version=version,
        persisted=True,
    )


@router.get("/current")
async def get_current_runtime_observability(
) -> dict:
    try:
        service = (
            get_runtime_observability_service()
        )

        current = service.get_current_metrics()
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    if current is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Runtime observability metrics "
                "have not been collected yet"
            ),
        )

    metrics, version = current

    return _metrics_response(
        metrics,
        metrics_version=version,
        persisted=True,
    )


@router.get("/history")
async def runtime_observability_history(
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
        service = (
            get_runtime_observability_service()
        )

        records = service.history(
            limit=limit,
            offset=offset,
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
        "count":
            len(records),
        "limit":
            limit,
        "offset":
            offset,
        "records":
            records,
        "safety": {
            "observability_only":
                True,
            "execution_enabled":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        },
    }
