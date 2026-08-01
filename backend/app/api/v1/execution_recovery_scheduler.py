from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.api.v1.execution_authorizations import (
    get_authorization_database_path,
)
from app.models.execution_recovery_scheduler import (
    ExecutionRecoveryScheduler,
    RecoverySchedulerVersionConflict,
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
from app.services.execution_recovery_scheduler import (
    ExecutionRecoverySchedulerService,
)
from app.services.execution_recovery_scheduler_store import (
    DEFAULT_RECOVERY_SCHEDULER_ID,
    ExecutionRecoverySchedulerStore,
)


router = APIRouter(
    prefix="/execution-recovery-scheduler",
    tags=["execution-recovery-scheduler"],
)


class SchedulerVersionPayload(BaseModel):
    expected_version: int = Field(
        ge=1,
    )


class SchedulerConfigurationPayload(BaseModel):
    expected_version: int = Field(
        ge=1,
    )

    interval_seconds: int | None = Field(
        default=None,
        ge=5,
        le=86400,
    )

    batch_size: int | None = Field(
        default=None,
        ge=1,
        le=1000,
    )


class SchedulerRunPayload(BaseModel):
    force: bool = False


def get_recovery_scheduler_store(
) -> ExecutionRecoverySchedulerStore:
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

    return ExecutionRecoverySchedulerStore(
        database_path
    )


def get_recovery_scheduler_service(
) -> ExecutionRecoverySchedulerService:
    database_path = (
        get_authorization_database_path()
    )

    store = get_recovery_scheduler_store()

    recovery_service = (
        ExecutionRecoveryService(
            database_path
        )
    )

    return ExecutionRecoverySchedulerService(
        database_path,
        scheduler_store=store,
        recovery_service=
            recovery_service,
    )


def _scheduler_not_found(
    scheduler_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            "Execution recovery scheduler "
            f"not found: {scheduler_id}"
        ),
    )


def _scheduler_response(
    scheduler: ExecutionRecoveryScheduler,
) -> dict:
    payload = scheduler.to_dict()

    payload["safety"] = {
        "background_loop_enabled":
            False,
        "manual_run_only":
            True,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return payload


def _scheduler_conflict(
    exc: Exception,
    *,
    conflict_type: str,
) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "type":
                conflict_type,
            "message":
                str(exc),
        },
    )


@router.get("")
async def get_execution_recovery_scheduler(
) -> dict:
    try:
        store = get_recovery_scheduler_store()

        scheduler = store.get(
            DEFAULT_RECOVERY_SCHEDULER_ID
        )

        if scheduler is None:
            scheduler = store.create_default()
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _scheduler_response(
        scheduler
    )


@router.post("/enable")
async def enable_execution_recovery_scheduler(
    payload: SchedulerVersionPayload,
) -> dict:
    try:
        store = get_recovery_scheduler_store()

        scheduler = store.get(
            DEFAULT_RECOVERY_SCHEDULER_ID
        )

        if scheduler is None:
            raise _scheduler_not_found(
                DEFAULT_RECOVERY_SCHEDULER_ID
            )

        updated = store.enable(
            DEFAULT_RECOVERY_SCHEDULER_ID,
            expected_version=(
                payload.expected_version
            ),
        )
    except HTTPException:
        raise
    except RecoverySchedulerVersionConflict as exc:
        raise _scheduler_conflict(
            exc,
            conflict_type=(
                "scheduler_version_conflict"
            ),
        ) from exc
    except ValueError as exc:
        raise _scheduler_conflict(
            exc,
            conflict_type=(
                "scheduler_enable_conflict"
            ),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _scheduler_response(
        updated
    )


@router.post("/disable")
async def disable_execution_recovery_scheduler(
    payload: SchedulerVersionPayload,
) -> dict:
    try:
        store = get_recovery_scheduler_store()

        scheduler = store.get(
            DEFAULT_RECOVERY_SCHEDULER_ID
        )

        if scheduler is None:
            raise _scheduler_not_found(
                DEFAULT_RECOVERY_SCHEDULER_ID
            )

        updated = store.disable(
            DEFAULT_RECOVERY_SCHEDULER_ID,
            expected_version=(
                payload.expected_version
            ),
        )
    except HTTPException:
        raise
    except RecoverySchedulerVersionConflict as exc:
        raise _scheduler_conflict(
            exc,
            conflict_type=(
                "scheduler_version_conflict"
            ),
        ) from exc
    except ValueError as exc:
        raise _scheduler_conflict(
            exc,
            conflict_type=(
                "scheduler_disable_conflict"
            ),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _scheduler_response(
        updated
    )


@router.patch("/configuration")
async def update_execution_recovery_scheduler(
    payload: SchedulerConfigurationPayload,
) -> dict:
    if (
        payload.interval_seconds is None
        and payload.batch_size is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "At least one scheduler "
                "configuration field is required"
            ),
        )

    try:
        store = get_recovery_scheduler_store()

        scheduler = store.get(
            DEFAULT_RECOVERY_SCHEDULER_ID
        )

        if scheduler is None:
            raise _scheduler_not_found(
                DEFAULT_RECOVERY_SCHEDULER_ID
            )

        updated = store.update_configuration(
            DEFAULT_RECOVERY_SCHEDULER_ID,
            expected_version=(
                payload.expected_version
            ),
            interval_seconds=(
                payload.interval_seconds
            ),
            batch_size=payload.batch_size,
        )
    except HTTPException:
        raise
    except RecoverySchedulerVersionConflict as exc:
        raise _scheduler_conflict(
            exc,
            conflict_type=(
                "scheduler_version_conflict"
            ),
        ) from exc
    except ValueError as exc:
        raise _scheduler_conflict(
            exc,
            conflict_type=(
                "scheduler_configuration_conflict"
            ),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _scheduler_response(
        updated
    )


@router.post("/run")
async def run_execution_recovery_scheduler(
    payload: SchedulerRunPayload,
) -> dict:
    try:
        service = (
            get_recovery_scheduler_service()
        )

        result = service.run_once(
            scheduler_id=(
                DEFAULT_RECOVERY_SCHEDULER_ID
            ),
            force=payload.force,
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

    response = result.to_dict()

    response["safety"] = {
        "background_loop_enabled":
            False,
        "manual_run_only":
            True,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return response


@router.get("/events")
async def execution_recovery_scheduler_events(
) -> dict:
    try:
        store = get_recovery_scheduler_store()

        scheduler = store.get(
            DEFAULT_RECOVERY_SCHEDULER_ID
        )

        if scheduler is None:
            raise _scheduler_not_found(
                DEFAULT_RECOVERY_SCHEDULER_ID
            )

        events = store.events(
            DEFAULT_RECOVERY_SCHEDULER_ID
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

    return {
        "scheduler_id":
            scheduler.scheduler_id,
        "count":
            len(events),
        "events":
            events,
    }
