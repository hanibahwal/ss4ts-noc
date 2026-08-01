from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.api.v1.execution_authorizations import (
    get_authorization_database_path,
)
from app.models.execution_recovery import (
    ExecutionRecovery,
    RecoveryStatus,
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


router = APIRouter(
    prefix="/execution-recovery",
    tags=["execution-recovery"],
)


class RunRecoveryPayload(BaseModel):
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
    )


def get_execution_recovery_service(
) -> ExecutionRecoveryService:
    database_path = (
        get_authorization_database_path()
    )

    # Initialize dependency schemas in order.
    ExecutionAuthorizationStore(
        database_path
    )

    ExecutionLeaseStore(
        database_path
    )

    ExecutionHeartbeatStore(
        database_path
    )

    return ExecutionRecoveryService(
        database_path
    )


def _recovery_not_found(
    recovery_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            "Execution recovery not found: "
            f"{recovery_id}"
        ),
    )


def _worker_not_found(
    worker_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            "Execution worker heartbeat "
            f"not found: {worker_id}"
        ),
    )


def _recovery_response(
    recovery: ExecutionRecovery,
) -> dict:
    payload = recovery.to_dict()

    payload["safety"] = {
        "recovery_coordination_only":
            True,
        "scheduler_enabled":
            False,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return payload


@router.post("/run")
async def run_stale_recovery(
    payload: RunRecoveryPayload,
) -> dict:
    """
    Recover stale workers discovered in the persistent store.

    This endpoint performs database coordination only. It does not
    execute commands or contact managed network devices.
    """

    try:
        service = (
            get_execution_recovery_service()
        )

        records = (
            service.recover_stale_workers(
                limit=payload.limit,
            )
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
        "recovered_count":
            sum(
                1
                for record in records
                if record.succeeded
            ),
        "skipped_count":
            sum(
                1
                for record in records
                if (
                    record.status
                    == RecoveryStatus.SKIPPED
                )
            ),
        "failed_count":
            sum(
                1
                for record in records
                if (
                    record.status
                    == RecoveryStatus.FAILED
                )
            ),
        "records": [
            _recovery_response(
                record
            )
            for record in records
        ],
        "safety": {
            "scheduler_enabled":
                False,
            "execution_enabled":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        },
    }


@router.post(
    "/workers/{worker_id}"
)
async def recover_execution_worker(
    worker_id: str,
) -> dict:
    try:
        service = (
            get_execution_recovery_service()
        )

        recovery = service.recover_worker(
            worker_id
        )
    except KeyError as exc:
        raise _worker_not_found(
            worker_id
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "recovery_conflict",
                "message":
                    str(exc),
                "worker_id":
                    worker_id,
            },
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _recovery_response(
        recovery
    )


@router.get("")
async def list_execution_recoveries(
    status: RecoveryStatus | None = None,
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
            get_execution_recovery_service()
        )

        records = service.list_recoveries(
            status=status,
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
        "records": [
            _recovery_response(
                record
            )
            for record in records
        ],
    }


@router.get(
    "/{recovery_id}"
)
async def get_execution_recovery(
    recovery_id: str,
) -> dict:
    try:
        service = (
            get_execution_recovery_service()
        )

        recovery = service.get(
            recovery_id
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

    if recovery is None:
        raise _recovery_not_found(
            recovery_id
        )

    return _recovery_response(
        recovery
    )


@router.get(
    "/{recovery_id}/events"
)
async def execution_recovery_events(
    recovery_id: str,
) -> dict:
    try:
        service = (
            get_execution_recovery_service()
        )

        recovery = service.get(
            recovery_id
        )

        if recovery is None:
            raise _recovery_not_found(
                recovery_id
            )

        events = service.events(
            recovery_id
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
        "recovery_id":
            recovery_id,
        "worker_id":
            recovery.worker_id,
        "lease_id":
            recovery.lease_id,
        "authorization_id":
            recovery.authorization_id,
        "count":
            len(events),
        "events":
            events,
    }
