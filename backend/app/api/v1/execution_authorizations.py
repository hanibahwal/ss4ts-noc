from __future__ import annotations

import os
from pathlib import Path
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

from app.api.v1.knowledge_graph import (
    build_runtime_graph,
)
from app.models.execution_concurrency import (
    AuthorizationVersionConflict,
    IdempotencyConflict,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationStatus,
)
from app.services.execution_authorization import (
    build_execution_authorization,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
    ExecutionAuthorizationStore,
)
from app.services.execution_planner import (
    build_execution_plan,
)


router = APIRouter(
    tags=["execution-authorizations"],
)


class RequesterPayload(BaseModel):
    identity_id: str = Field(
        min_length=1,
        max_length=200,
    )

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    role: ApprovalRole

    email: str | None = Field(
        default=None,
        max_length=320,
    )


class ApproverPayload(BaseModel):
    identity_id: str = Field(
        min_length=1,
        max_length=200,
    )

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    role: ApprovalRole

    email: str | None = Field(
        default=None,
        max_length=320,
    )


class CreateAuthorizationPayload(BaseModel):
    requester: RequesterPayload

    ttl_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
    )


class ApprovalPayload(BaseModel):
    approver: ApproverPayload

    expected_version: int = Field(
        ge=1,
    )

    idempotency_key: str = Field(
        min_length=1,
        max_length=200,
    )


class RejectionPayload(BaseModel):
    approver: ApproverPayload

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )


class RevocationPayload(BaseModel):
    actor: ApproverPayload

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )


def get_authorization_database_path() -> Path:
    configured = os.getenv(
        "SS4TS_EXECUTION_AUTH_DB",
        str(
            DEFAULT_AUTHORIZATION_DATABASE
        ),
    ).strip()

    if not configured:
        raise RuntimeError(
            "SS4TS_EXECUTION_AUTH_DB "
            "must not be empty"
        )

    return Path(configured)


def get_authorization_store(
) -> ExecutionAuthorizationStore:
    return ExecutionAuthorizationStore(
        get_authorization_database_path()
    )


def _identity(
    payload: (
        RequesterPayload
        | ApproverPayload
    ),
) -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id=payload.identity_id,
        display_name=payload.display_name,
        role=payload.role,
        email=payload.email,
    )


def _response(
    authorization,
    *,
    store: ExecutionAuthorizationStore,
) -> dict:
    payload = authorization.to_dict()

    payload["record_version"] = (
        store.get_record_version(
            authorization.authorization_id
        )
    )

    payload["verified"] = store.verify(
        authorization.authorization_id
    )

    payload["safety"] = {
        "authorization_management_only":
            True,
        "execution_enabled":
            False,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    return payload


def _not_found(
    authorization_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=(
            "Execution authorization "
            f"not found: {authorization_id}"
        ),
    )


@router.post(
    "/knowledge-graph/nodes/{node_id}/"
    "execution-authorization"
)
async def create_execution_authorization(
    node_id: str,
    payload: CreateAuthorizationPayload,
    max_depth: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 10,
    refresh: bool = False,
) -> dict:
    """
    Build and persist an execution-authorization request.

    This endpoint generates a dry-run execution plan and authorization
    request only. It never executes a managed-device command.
    """

    graph = await build_runtime_graph(
        refresh=refresh
    )

    try:
        plan = build_execution_plan(
            graph,
            node_id,
            max_depth=max_depth,
        )

        authorization = (
            build_execution_authorization(
                plan,
                requester=_identity(
                    payload.requester
                ),
                ttl_minutes=
                    payload.ttl_minutes,
            )
        )

        store = get_authorization_store()

        created = store.create(
            authorization
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Graph node not found: "
                f"{node_id}"
            ),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _response(
        created,
        store=store,
    )


@router.get(
    "/execution-authorizations"
)
async def list_execution_authorizations(
    status: AuthorizationStatus | None = None,
    source_node_id: str | None = None,
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
        store = get_authorization_store()

        store.expire_due()

        records = store.list_authorizations(
            status=status,
            source_node_id=
                source_node_id,
            limit=limit,
            offset=offset,
        )

        total = store.count(
            status=status
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
        "count": len(records),
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": [
            {
                "authorization_id":
                    item.authorization_id,
                "plan_id":
                    item.plan_id,
                "decision_id":
                    item.decision_id,
                "source_node_id":
                    item.source_node_id,
                "risk_class":
                    item.risk_class.value,
                "status":
                    item.status.value,
                "decision":
                    item.decision.value,
                "requested_at":
                    item.requested_at
                    .isoformat(),
                "expires_at": (
                    item.expires_at
                    .isoformat()
                    if item.expires_at
                    else None
                ),
                "required_role":
                    item.metadata.get(
                        "required_role"
                    ),
                "record_version":
                    store.get_record_version(
                        item.authorization_id
                    ),
                "is_expired":
                    item.is_expired,
                "is_usable":
                    item.is_usable,
            }
            for item in records
        ],
    }


@router.get(
    "/execution-authorizations/"
    "{authorization_id}"
)
async def get_execution_authorization(
    authorization_id: str,
) -> dict:
    try:
        store = get_authorization_store()

        store.expire_due()

        authorization = store.get(
            authorization_id
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

    if authorization is None:
        raise _not_found(
            authorization_id
        )

    return _response(
        authorization,
        store=store,
    )


@router.post(
    "/execution-authorizations/"
    "{authorization_id}/approve"
)
async def approve_execution_authorization(
    authorization_id: str,
    payload: ApprovalPayload,
) -> dict:
    try:
        store = get_authorization_store()

        mutation = store.approve_atomic(
            authorization_id,
            approver=_identity(
                payload.approver
            ),
            expected_version=
                payload.expected_version,
            idempotency_key=
                payload.idempotency_key,
        )

        approved = store.get(
            authorization_id
        )

        if approved is None:
            raise _not_found(
                authorization_id
            )
    except KeyError as exc:
        raise _not_found(
            authorization_id
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except AuthorizationVersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "version_conflict",
                "message":
                    str(exc),
                "authorization_id":
                    exc.authorization_id,
                "expected_version":
                    exc.expected_version,
                "actual_version":
                    exc.actual_version,
            },
        ) from exc
    except IdempotencyConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "idempotency_conflict",
                "message":
                    str(exc),
                "idempotency_key":
                    exc.idempotency_key,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    response = _response(
        approved,
        store=store,
    )

    response["mutation"] = (
        mutation.to_dict()
    )

    return response


@router.post(
    "/execution-authorizations/"
    "{authorization_id}/reject"
)
async def reject_execution_authorization(
    authorization_id: str,
    payload: RejectionPayload,
) -> dict:
    try:
        store = get_authorization_store()

        rejected = store.reject(
            authorization_id,
            approver=_identity(
                payload.approver
            ),
            reason=payload.reason,
        )
    except KeyError as exc:
        raise _not_found(
            authorization_id
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _response(
        rejected,
        store=store,
    )


@router.post(
    "/execution-authorizations/"
    "{authorization_id}/revoke"
)
async def revoke_execution_authorization(
    authorization_id: str,
    payload: RevocationPayload,
) -> dict:
    try:
        store = get_authorization_store()

        revoked = store.revoke(
            authorization_id,
            actor=_identity(
                payload.actor
            ),
            reason=payload.reason,
        )
    except KeyError as exc:
        raise _not_found(
            authorization_id
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return _response(
        revoked,
        store=store,
    )


@router.get(
    "/execution-authorizations/"
    "{authorization_id}/events"
)
async def execution_authorization_events(
    authorization_id: str,
) -> dict:
    try:
        store = get_authorization_store()

        authorization = store.get(
            authorization_id
        )

        if authorization is None:
            raise _not_found(
                authorization_id
            )

        events = store.events(
            authorization_id
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
        "authorization_id":
            authorization_id,
        "count":
            len(events),
        "events":
            events,
    }


@router.get(
    "/execution-authorizations/"
    "{authorization_id}/verify"
)
async def verify_execution_authorization(
    authorization_id: str,
) -> dict:
    try:
        store = get_authorization_store()

        authorization = store.get(
            authorization_id
        )

        if authorization is None:
            raise _not_found(
                authorization_id
            )

        verified = store.verify(
            authorization_id
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
        "authorization_id":
            authorization_id,
        "verified":
            verified,
        "integrity_status": (
            "valid"
            if verified
            else "corrupted"
        ),
        "checksum_algorithm":
            "sha256",
    }
