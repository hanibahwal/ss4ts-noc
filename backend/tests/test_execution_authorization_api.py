from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import (
    execution_authorizations,
)
from app.api.v1.router import api_router
from app.models.execution_authorization import (
    ApprovalRole,
)
from tests.test_decision_fusion import (
    make_graph,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


def requester_payload():
    return (
        execution_authorizations
        .CreateAuthorizationPayload(
            requester=(
                execution_authorizations
                .RequesterPayload(
                    identity_id="user:hani",
                    display_name="Hani",
                    role=(
                        ApprovalRole
                        .NETWORK_ENGINEER
                    ),
                )
            ),
            ttl_minutes=30,
        )
    )


def approver_payload(
    role: ApprovalRole = (
        ApprovalRole.SENIOR_ENGINEER
    ),
    *,
    expected_version: int = 1,
    idempotency_key: str = (
        "approve-api-001"
    ),
    identity_id: str = (
        "user:approver"
    ),
):
    return (
        execution_authorizations
        .ApprovalPayload(
            approver=(
                execution_authorizations
                .ApproverPayload(
                    identity_id=
                        identity_id,
                    display_name="Approver",
                    role=role,
                )
            ),
            expected_version=
                expected_version,
            idempotency_key=
                idempotency_key,
        )
    )


@pytest.fixture
def authorization_environment(
    tmp_path,
    monkeypatch,
):
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    monkeypatch.setenv(
        "SS4TS_EXECUTION_AUTH_DB",
        str(database),
    )

    async def fake_graph(
        *,
        refresh: bool = False,
    ):
        del refresh

        return make_graph(
            power_alarm=True
        )

    monkeypatch.setattr(
        execution_authorizations,
        "build_runtime_graph",
        fake_graph,
    )

    return database


def test_create_authorization(
    authorization_environment,
) -> None:
    result = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    assert result["authorization_id"]

    assert result["status"] == "pending"

    assert (
        result["decision"]
        == "require_approval"
    )

    assert (
        result["metadata"]
        ["required_role"]
        == "senior_engineer"
    )

    assert result["verified"] is True

    assert (
        result["safety"]
        ["device_command_executed"]
        is False
    )


def test_list_authorizations(
    authorization_environment,
) -> None:
    run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    result = run(
        execution_authorizations
        .list_execution_authorizations(
            status=None,
            source_node_id=
                "device:core",
            limit=100,
            offset=0,
        )
    )

    assert result["count"] == 1
    assert result["total"] == 1


def test_get_authorization(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    loaded = run(
        execution_authorizations
        .get_execution_authorization(
            created[
                "authorization_id"
            ]
        )
    )

    assert (
        loaded["authorization_id"]
        == created["authorization_id"]
    )

    assert loaded["verified"] is True


def test_senior_can_approve(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    approved = run(
        execution_authorizations
        .approve_execution_authorization(
            created[
                "authorization_id"
            ],
            approver_payload(),
        )
    )

    assert approved["status"] == "approved"
    assert approved["decision"] == "allow"
    assert approved["is_usable"] is True

    assert (
        approved["safety"]
        ["execution_enabled"]
        is False
    )


def test_insufficient_role_returns_403(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_authorizations
            .approve_execution_authorization(
                created[
                    "authorization_id"
                ],
                approver_payload(
                    ApprovalRole
                    .NETWORK_ENGINEER
                ),
            )
        )

    assert exc.value.status_code == 403


def test_reject_authorization(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    payload = (
        execution_authorizations
        .RejectionPayload(
            approver=(
                execution_authorizations
                .ApproverPayload(
                    identity_id="user:senior",
                    display_name="Senior",
                    role=(
                        ApprovalRole
                        .SENIOR_ENGINEER
                    ),
                )
            ),
            reason="Maintenance window unavailable",
        )
    )

    rejected = run(
        execution_authorizations
        .reject_execution_authorization(
            created[
                "authorization_id"
            ],
            payload,
        )
    )

    assert rejected["status"] == "rejected"

    assert (
        rejected["rejection_reason"]
        == "Maintenance window unavailable"
    )


def test_revoke_authorization(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    approved = run(
        execution_authorizations
        .approve_execution_authorization(
            created[
                "authorization_id"
            ],
            approver_payload(),
        )
    )

    payload = (
        execution_authorizations
        .RevocationPayload(
            actor=(
                execution_authorizations
                .ApproverPayload(
                    identity_id="user:senior",
                    display_name="Senior",
                    role=(
                        ApprovalRole
                        .SENIOR_ENGINEER
                    ),
                )
            ),
            reason="Network state changed",
        )
    )

    revoked = run(
        execution_authorizations
        .revoke_execution_authorization(
            approved[
                "authorization_id"
            ],
            payload,
        )
    )

    assert revoked["status"] == "revoked"
    assert revoked["is_usable"] is False


def test_authorization_events(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    run(
        execution_authorizations
        .approve_execution_authorization(
            created[
                "authorization_id"
            ],
            approver_payload(),
        )
    )

    result = run(
        execution_authorizations
        .execution_authorization_events(
            created[
                "authorization_id"
            ]
        )
    )

    assert [
        item["event_type"]
        for item in result["events"]
    ] == [
        "created",
        "approved",
    ]


def test_verify_authorization(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    result = run(
        execution_authorizations
        .verify_execution_authorization(
            created[
                "authorization_id"
            ]
        )
    )

    assert result["verified"] is True

    assert (
        result["integrity_status"]
        == "valid"
    )


def test_missing_authorization_returns_404(
    authorization_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_authorizations
            .get_execution_authorization(
                "authorization:missing"
            )
        )

    assert exc.value.status_code == 404


def test_unknown_node_returns_404(
    authorization_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_authorizations
            .create_execution_authorization(
                "device:missing",
                requester_payload(),
                max_depth=10,
                refresh=False,
            )
        )

    assert exc.value.status_code == 404


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/knowledge-graph/"
            "nodes/{node_id}/"
            "execution-authorization"
        ),
        "/api/v1/execution-authorizations",
        (
            "/api/v1/execution-authorizations/"
            "{authorization_id}"
        ),
        (
            "/api/v1/execution-authorizations/"
            "{authorization_id}/approve"
        ),
        (
            "/api/v1/execution-authorizations/"
            "{authorization_id}/reject"
        ),
        (
            "/api/v1/execution-authorizations/"
            "{authorization_id}/revoke"
        ),
        (
            "/api/v1/execution-authorizations/"
            "{authorization_id}/events"
        ),
        (
            "/api/v1/execution-authorizations/"
            "{authorization_id}/verify"
        ),
    }

    assert expected.issubset(paths)

def test_approval_returns_new_mutation(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    approved = run(
        execution_authorizations
        .approve_execution_authorization(
            created["authorization_id"],
            approver_payload(
                idempotency_key=
                    "approve-new-001"
            ),
        )
    )

    assert approved["record_version"] == 2

    assert (
        approved["mutation"]["disposition"]
        == "new"
    )

    assert (
        approved["mutation"]["current_version"]
        == 2
    )


def test_same_approval_request_is_replayed(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    payload = approver_payload(
        idempotency_key=
            "approve-replay-api-001"
    )

    first = run(
        execution_authorizations
        .approve_execution_authorization(
            created["authorization_id"],
            payload,
        )
    )

    replay = run(
        execution_authorizations
        .approve_execution_authorization(
            created["authorization_id"],
            payload,
        )
    )

    assert (
        first["mutation"]["disposition"]
        == "new"
    )

    assert (
        replay["mutation"]["disposition"]
        == "replay"
    )

    assert replay["record_version"] == 2


def test_stale_approval_version_returns_409(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    run(
        execution_authorizations
        .approve_execution_authorization(
            created["authorization_id"],
            approver_payload(
                idempotency_key=
                    "approve-version-api-001"
            ),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_authorizations
            .approve_execution_authorization(
                created["authorization_id"],
                approver_payload(
                    expected_version=1,
                    idempotency_key=
                        "approve-version-api-002",
                ),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "version_conflict"
    )

    assert (
        exc.value.detail["actual_version"]
        == 2
    )


def test_idempotency_key_conflict_returns_409(
    authorization_environment,
) -> None:
    created = run(
        execution_authorizations
        .create_execution_authorization(
            "device:core",
            requester_payload(),
            max_depth=10,
            refresh=False,
        )
    )

    run(
        execution_authorizations
        .approve_execution_authorization(
            created["authorization_id"],
            approver_payload(
                idempotency_key=
                    "approve-key-api-001",
                identity_id=
                    "user:first",
            ),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_authorizations
            .approve_execution_authorization(
                created["authorization_id"],
                approver_payload(
                    idempotency_key=
                        "approve-key-api-001",
                    identity_id=
                        "user:second",
                ),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "idempotency_conflict"
    )
