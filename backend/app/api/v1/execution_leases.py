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
from app.models.execution_lease import (
    ExecutionLease,
    ExecutionLeaseStatus,
    LeaseConflict,
    LeaseTokenMismatch,
    LeaseVersionConflict,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_lease_store import (
    DEFAULT_EXECUTION_LEASE_TTL_SECONDS,
    ExecutionLeaseStore,
)


router = APIRouter(
    tags=["execution-leases"],
)


class AcquireLeasePayload(BaseModel):
    owner_id: str = Field(
        min_length=1,
        max_length=200,
    )

    ttl_seconds: int = Field(
        default=(
            DEFAULT_EXECUTION_LEASE_TTL_SECONDS
        ),
        ge=5,
        le=3600,
    )


class RenewLeasePayload(BaseModel):
    lease_token: str = Field(
        min_length=1,
        max_length=500,
    )

    expected_version: int = Field(
        ge=1,
    )

    ttl_seconds: int = Field(
        default=(
            DEFAULT_EXECUTION_LEASE_TTL_SECONDS
        ),
        ge=5,
        le=3600,
    )


class ReleaseLeasePayload(BaseModel):
    lease_token: str = Field(
        min_length=1,
        max_length=500,
    )

    expected_version: int = Field(
        ge=1,
    )


class VerifyLeasePayload(BaseModel):
    lease_token: str = Field(
        min_length=1,
        max_length=500,
    )


def get_execution_lease_store(
) -> ExecutionLeaseStore:
    database_path = (
        get_authorization_database_path()
    )

    # Ensure the parent authorization schema exists before the
    # lease store validates its foreign-key dependency.
    ExecutionAuthorizationStore(
        database_path
    )

    return ExecutionLeaseStore(
        database_path
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


def _authorization_not_found(
    authorization_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            "Execution authorization "
            f"not found: {authorization_id}"
        ),
    )


def _lease_response(
    lease: ExecutionLease,
    *,
    include_token: bool = False,
) -> dict:
    payload = lease.to_dict()

    if not include_token:
        payload.pop(
            "lease_token",
            None,
        )

    payload["token_exposed"] = (
        include_token
    )

    payload["safety"] = {
        "lease_coordination_only":
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
    "/execution-authorizations/"
    "{authorization_id}/lease"
)
async def acquire_execution_lease(
    authorization_id: str,
    payload: AcquireLeasePayload,
) -> dict:
    """
    Acquire an atomic execution lease.

    This endpoint reserves authorization ownership only. It does not
    execute commands or contact a managed network device.
    """

    try:
        store = get_execution_lease_store()

        lease = store.acquire(
            authorization_id,
            owner_id=payload.owner_id,
            ttl_seconds=
                payload.ttl_seconds,
        )
    except KeyError as exc:
        raise _authorization_not_found(
            authorization_id
        ) from exc
    except LeaseConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "lease_conflict",
                "message":
                    str(exc),
                "authorization_id":
                    exc.authorization_id,
                "owner_id":
                    exc.owner_id,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "authorization_not_usable",
                "message":
                    str(exc),
                "authorization_id":
                    authorization_id,
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

    return _lease_response(
        lease,
        include_token=True,
    )


@router.get(
    "/execution-leases"
)
async def list_execution_leases(
    authorization_id: str | None = None,
    owner_id: str | None = None,
    status: ExecutionLeaseStatus | None = None,
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
        store = get_execution_lease_store()

        store.expire_due()

        records = store.list_leases(
            authorization_id=
                authorization_id,
            owner_id=owner_id,
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
            _lease_response(
                lease,
                include_token=False,
            )
            for lease in records
        ],
    }


@router.get(
    "/execution-leases/{lease_id}"
)
async def get_execution_lease(
    lease_id: str,
) -> dict:
    try:
        store = get_execution_lease_store()

        store.expire_due()

        lease = store.get(
            lease_id
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

    if lease is None:
        raise _lease_not_found(
            lease_id
        )

    return _lease_response(
        lease,
        include_token=False,
    )


@router.post(
    "/execution-leases/{lease_id}/renew"
)
async def renew_execution_lease(
    lease_id: str,
    payload: RenewLeasePayload,
) -> dict:
    try:
        store = get_execution_lease_store()

        renewed = store.renew(
            lease_id,
            lease_token=
                payload.lease_token,
            expected_version=
                payload.expected_version,
            ttl_seconds=
                payload.ttl_seconds,
        )
    except KeyError as exc:
        raise _lease_not_found(
            lease_id
        ) from exc
    except LeaseTokenMismatch as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "type":
                    "lease_token_mismatch",
                "message":
                    str(exc),
                "lease_id":
                    exc.lease_id,
            },
        ) from exc
    except LeaseVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "lease_version_conflict",
                "message":
                    str(exc),
                "lease_id":
                    exc.lease_id,
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
                    "lease_not_active",
                "message":
                    str(exc),
                "lease_id":
                    lease_id,
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

    return _lease_response(
        renewed,
        include_token=True,
    )


@router.post(
    "/execution-leases/{lease_id}/release"
)
async def release_execution_lease(
    lease_id: str,
    payload: ReleaseLeasePayload,
) -> dict:
    try:
        store = get_execution_lease_store()

        released = store.release(
            lease_id,
            lease_token=
                payload.lease_token,
            expected_version=
                payload.expected_version,
        )
    except KeyError as exc:
        raise _lease_not_found(
            lease_id
        ) from exc
    except LeaseTokenMismatch as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "type":
                    "lease_token_mismatch",
                "message":
                    str(exc),
                "lease_id":
                    exc.lease_id,
            },
        ) from exc
    except LeaseVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "lease_version_conflict",
                "message":
                    str(exc),
                "lease_id":
                    exc.lease_id,
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
                    "lease_not_active",
                "message":
                    str(exc),
                "lease_id":
                    lease_id,
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

    return _lease_response(
        released,
        include_token=True,
    )


@router.get(
    "/execution-leases/{lease_id}/events"
)
async def execution_lease_events(
    lease_id: str,
) -> dict:
    try:
        store = get_execution_lease_store()

        lease = store.get(
            lease_id
        )

        if lease is None:
            raise _lease_not_found(
                lease_id
            )

        events = store.events(
            lease_id
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
        "lease_id":
            lease_id,
        "authorization_id":
            lease.authorization_id,
        "count":
            len(events),
        "events":
            events,
    }


@router.post(
    "/execution-leases/{lease_id}/verify"
)
async def verify_execution_lease(
    lease_id: str,
    payload: VerifyLeasePayload,
) -> dict:
    try:
        store = get_execution_lease_store()

        lease = store.get(
            lease_id
        )

        if lease is None:
            raise _lease_not_found(
                lease_id
            )

        token_valid = store.verify_token(
            lease_id,
            lease_token=
                payload.lease_token,
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
        "lease_id":
            lease_id,
        "authorization_id":
            lease.authorization_id,
        "token_valid":
            token_valid,
        "status":
            lease.status.value,
        "lease_version":
            lease.lease_version,
        "is_active":
            lease.is_active,
        "is_expired":
            lease.is_expired,
    }
