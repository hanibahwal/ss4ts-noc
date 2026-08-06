from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.services.controlled_execution_recovery_runtime import (
    ControlledExecutionRecoveryRuntime,
    get_controlled_recovery_runtime,
    runtime_enabled_from_environment,
)


router = APIRouter(
    prefix=(
        "/remediation/"
        "controlled-recovery-runtime"
    ),
    tags=[
        "controlled-execution-recovery-runtime"
    ],
)


def get_runtime(
) -> ControlledExecutionRecoveryRuntime:
    return get_controlled_recovery_runtime()


def _runtime_response(
    runtime: ControlledExecutionRecoveryRuntime,
) -> dict:
    payload = runtime.snapshot()

    payload["environment_enabled"] = (
        runtime_enabled_from_environment()
    )

    payload["safety"] = {
        "runtime_environment_required":
            True,
        "fail_closed":
            True,
        "simulation_only":
            True,
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
async def get_controlled_recovery_runtime(
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
async def start_controlled_recovery_runtime(
) -> dict:
    if not runtime_enabled_from_environment():
        raise _runtime_conflict(
            conflict_type=(
                "runtime_environment_disabled"
            ),
            message=(
                "Controlled execution recovery "
                "runtime is disabled by environment"
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
                    "Controlled execution recovery "
                    "runtime is already running"
                ),
            )

        started = await runtime.start()

        if not started:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_start_conflict"
                ),
                message=(
                    "Controlled execution recovery "
                    "runtime could not be started"
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
async def stop_controlled_recovery_runtime(
) -> dict:
    try:
        runtime = get_runtime()

        if not runtime.is_running:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_already_stopped"
                ),
                message=(
                    "Controlled execution recovery "
                    "runtime is already stopped"
                ),
            )

        stopped = await runtime.stop()

        if not stopped:
            raise _runtime_conflict(
                conflict_type=(
                    "runtime_stop_conflict"
                ),
                message=(
                    "Controlled execution recovery "
                    "runtime could not be stopped"
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


@router.post("/run-cycle")
async def run_controlled_recovery_cycle(
) -> dict:
    try:
        runtime = get_runtime()

        result = await runtime.run_cycle()

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
        "runtime":
            _runtime_response(
                runtime
            ),
        "result":
            result,
    }
