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
from app.models.execution_heartbeat import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ExecutionWorkerHeartbeat,
    WorkerHeartbeatOwnerMismatch,
    WorkerHeartbeatStatus,
    WorkerHeartbeatVersionConflict,
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


router = APIRouter(
    tags=["execution-heartbeats"],
)


class RegisterHeartbeatPayload(BaseModel):
    worker_id: str = Field(
        min_length=1,
        max_length=200,
    )

    heartbeat_interval_seconds: int = Field(
        default=(
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS
        ),
        ge=1,
        le=3600,
    )

    heartbeat_timeout_seconds: int = Field(
        default=(
            DEFAULT_HEARTBEAT_TIMEOUT_SECONDS
        ),
        ge=2,
        le=7200,
    )

    metadata: dict = Field(
        default_factory=dict,
    )


class RecordHeartbeatPayload(BaseModel):
    expected_version: int = Field(
        ge=1,
    )


class StopWorkerPayload(BaseModel):
    expected_version: int = Field(
        ge=1,
    )

    reason: str | None = Field(
        default=None,
        max_length=500,
    )


def get_execution_heartbeat_store(
) -> ExecutionHeartbeatStore:
    database_path = (
        get_authorization_database_path()
    )

    # Initialize parent schemas in dependency order.
    ExecutionAuthorizationStore(
        database_path
    )

    ExecutionLeaseStore(
        database_path
    )

    return ExecutionHeartbeatStore(
        database_path
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


def _lease_not_found(
    lease_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            "Execution lease not found: "
            f"{lease_id}"
        ),
    )


def _heartbeat_response(
    heartbeat: ExecutionWorkerHeartbeat,
) -> dict:
    payload = heartbeat.to_dict()

    payload["safety"] = {
        "heartbeat_coordination_only":
            True,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return payload


@router.post(
    "/execution-leases/"
    "{lease_id}/heartbeat/register"
)
async def register_execution_worker(
    lease_id: str,
    payload: RegisterHeartbeatPayload,
) -> dict:
    """
    Register a worker heartbeat against an active execution lease.

    Registration performs coordination only and never executes
    managed-device commands.
    """

    try:
        store = get_execution_heartbeat_store()

        heartbeat = store.register_worker(
            worker_id=payload.worker_id,
            lease_id=lease_id,
            heartbeat_interval_seconds=(
                payload
                .heartbeat_interval_seconds
            ),
            heartbeat_timeout_seconds=(
                payload
                .heartbeat_timeout_seconds
            ),
            metadata=payload.metadata,
        )
    except KeyError as exc:
        raise _lease_not_found(
            lease_id
        ) from exc
    except WorkerHeartbeatOwnerMismatch as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "type":
                    "heartbeat_owner_mismatch",
                "message":
                    str(exc),
                "worker_id":
                    exc.worker_id,
                "lease_owner_id":
                    exc.lease_owner_id,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "heartbeat_registration_conflict",
                "message":
                    str(exc),
                "lease_id":
                    lease_id,
                "worker_id":
                    payload.worker_id,
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

    return _heartbeat_response(
        heartbeat
    )


@router.post(
    "/execution-workers/"
    "{worker_id}/heartbeat"
)
async def record_execution_worker_heartbeat(
    worker_id: str,
    payload: RecordHeartbeatPayload,
) -> dict:
    try:
        store = get_execution_heartbeat_store()

        heartbeat = store.record_heartbeat(
            worker_id,
            expected_version=(
                payload.expected_version
            ),
        )
    except KeyError as exc:
        raise _worker_not_found(
            worker_id
        ) from exc
    except WorkerHeartbeatOwnerMismatch as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "type":
                    "heartbeat_owner_mismatch",
                "message":
                    str(exc),
                "worker_id":
                    exc.worker_id,
                "lease_owner_id":
                    exc.lease_owner_id,
            },
        ) from exc
    except WorkerHeartbeatVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "heartbeat_version_conflict",
                "message":
                    str(exc),
                "worker_id":
                    exc.worker_id,
                "expected_version":
                    exc.expected_version,
                "actual_version":
                    exc.actual_version,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "heartbeat_not_allowed",
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

    return _heartbeat_response(
        heartbeat
    )


@router.post(
    "/execution-workers/{worker_id}/stop"
)
async def stop_execution_worker(
    worker_id: str,
    payload: StopWorkerPayload,
) -> dict:
    try:
        store = get_execution_heartbeat_store()

        heartbeat = store.stop_worker(
            worker_id,
            expected_version=(
                payload.expected_version
            ),
            reason=payload.reason,
        )
    except KeyError as exc:
        raise _worker_not_found(
            worker_id
        ) from exc
    except WorkerHeartbeatVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "heartbeat_version_conflict",
                "message":
                    str(exc),
                "worker_id":
                    exc.worker_id,
                "expected_version":
                    exc.expected_version,
                "actual_version":
                    exc.actual_version,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "heartbeat_stop_conflict",
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

    return _heartbeat_response(
        heartbeat
    )


@router.get(
    "/execution-workers"
)
async def list_execution_workers(
    authorization_id: str | None = None,
    lease_id: str | None = None,
    status: WorkerHeartbeatStatus | None = None,
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
        store = get_execution_heartbeat_store()

        records = store.list_workers(
            authorization_id=
                authorization_id,
            lease_id=lease_id,
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
            _heartbeat_response(
                heartbeat
            )
            for heartbeat in records
        ],
    }


# Keep this static path before /{worker_id}.
@router.get(
    "/execution-workers/stale"
)
async def stale_execution_workers(
) -> dict:
    try:
        store = get_execution_heartbeat_store()

        records = store.stale_workers()
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
        "records": [
            _heartbeat_response(
                heartbeat
            )
            for heartbeat in records
        ],
    }


@router.get(
    "/execution-workers/{worker_id}"
)
async def get_execution_worker(
    worker_id: str,
) -> dict:
    try:
        store = get_execution_heartbeat_store()

        heartbeat = store.get(
            worker_id
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

    if heartbeat is None:
        raise _worker_not_found(
            worker_id
        )

    return _heartbeat_response(
        heartbeat
    )


@router.get(
    "/execution-workers/"
    "{worker_id}/events"
)
async def execution_worker_events(
    worker_id: str,
) -> dict:
    try:
        store = get_execution_heartbeat_store()

        heartbeat = store.get(
            worker_id
        )

        if heartbeat is None:
            raise _worker_not_found(
                worker_id
            )

        events = store.events(
            worker_id
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
        "worker_id":
            worker_id,
        "lease_id":
            heartbeat.lease_id,
        "authorization_id":
            heartbeat.authorization_id,
        "count":
            len(events),
        "events":
            events,
    }
