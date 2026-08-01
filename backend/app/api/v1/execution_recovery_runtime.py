from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.api.v1.execution_authorizations import (
    get_authorization_database_path,
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
    ExecutionRecoverySchedulerRuntime,
    get_recovery_scheduler_runtime,
    runtime_enabled_from_environment,
)
from app.services.execution_recovery_scheduler_store import (
    ExecutionRecoverySchedulerStore,
)


router = APIRouter(
    prefix="/execution-recovery-runtime",
    tags=["execution-recovery-runtime"],
)


def get_runtime(
) -> ExecutionRecoverySchedulerRuntime:
    database_path = (
        get_authorization_database_path()
    )

    # Initialize dependency schemas in the required order.
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

    ExecutionRecoverySchedulerStore(
        database_path
    )

    return get_recovery_scheduler_runtime(
        database_path
    )


def _runtime_response(
    runtime: ExecutionRecoverySchedulerRuntime,
) -> dict:
    payload = runtime.snapshot()

    payload["environment_enabled"] = (
        runtime_enabled_from_environment()
    )

    payload["is_running"] = (
        runtime.is_running
    )

    payload["safety"] = {
        "runtime_environment_required":
            True,
        "runtime_control_only":
            True,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return payload


def _runtime_conflict(
    *,
    conflict_type: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "type":
                conflict_type,
            "message":
                message,
        },
    )


@router.get("")
async def get_execution_recovery_runtime(
) -> dict:
    try:
        runtime = get_runtime()
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _runtime_response(
        runtime
    )


@router.post("/start")
async def start_execution_recovery_runtime(
) -> dict:
    if not runtime_enabled_from_environment():
        raise _runtime_conflict(
            conflict_type=(
                "runtime_environment_disabled"
            ),
            message=(
                "Recovery scheduler runtime "
                "is disabled by environment"
            ),
        )

    try:
        runtime = get_runtime()

        if runtime.is_running:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_already_running"
                ),
                message=(
                    "Recovery scheduler runtime "
                    "is already running"
                ),
            )

        started = await runtime.start()

        if not started:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_start_conflict"
                ),
                message=(
                    "Recovery scheduler runtime "
                    "could not be started"
                ),
            )

    except HTTPException:
        raise
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _runtime_response(
        runtime
    )


@router.post("/stop")
async def stop_execution_recovery_runtime(
) -> dict:
    try:
        runtime = get_runtime()

        if not runtime.is_running:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_already_stopped"
                ),
                message=(
                    "Recovery scheduler runtime "
                    "is already stopped"
                ),
            )

        stopped = await runtime.stop()

        if not stopped:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_stop_conflict"
                ),
                message=(
                    "Recovery scheduler runtime "
                    "could not be stopped"
                ),
            )

    except HTTPException:
        raise
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _runtime_response(
        runtime
    )
