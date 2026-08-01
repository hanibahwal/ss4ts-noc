from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import (
    execution_leases,
)
from app.api.v1.router import (
    api_router,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
)
from app.services.execution_authorization import (
    build_execution_authorization,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from tests.test_execution_simulator import (
    make_plan,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


def requester() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:hani",
        display_name="Hani",
        role=ApprovalRole.NETWORK_ENGINEER,
    )


def senior() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:senior",
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )


@pytest.fixture
def lease_environment(
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

    authorization_store = (
        ExecutionAuthorizationStore(
            database
        )
    )

    lease_store = ExecutionLeaseStore(
        database
    )

    authorization = (
        authorization_store.create(
            build_execution_authorization(
                make_plan(),
                requester=requester(),
            )
        )
    )

    authorization_store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=(
            "approve-lease-api-001"
        ),
    )

    return {
        "database":
            database,
        "authorization_store":
            authorization_store,
        "lease_store":
            lease_store,
        "authorization_id":
            authorization.authorization_id,
    }


def acquire_payload(
    *,
    owner_id: str = "worker:1",
    ttl_seconds: int = 60,
):
    return (
        execution_leases
        .AcquireLeasePayload(
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
        )
    )


def test_acquire_lease(
    lease_environment,
) -> None:
    result = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    assert result["lease_id"]
    assert result["status"] == "active"
    assert result["owner_id"] == "worker:1"
    assert result["lease_version"] == 1
    assert result["lease_token"]
    assert result["token_exposed"] is True

    assert (
        result["safety"]
        ["execution_enabled"]
        is False
    )


def test_get_hides_token(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    loaded = run(
        execution_leases
        .get_execution_lease(
            created["lease_id"]
        )
    )

    assert (
        loaded["lease_id"]
        == created["lease_id"]
    )

    assert "lease_token" not in loaded
    assert loaded["token_exposed"] is False


def test_list_hides_tokens(
    lease_environment,
) -> None:
    run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    result = run(
        execution_leases
        .list_execution_leases(
            authorization_id=(
                lease_environment[
                    "authorization_id"
                ]
            ),
            owner_id=None,
            status=None,
            limit=100,
            offset=0,
        )
    )

    assert result["count"] == 1
    assert "lease_token" not in (
        result["records"][0]
    )


def test_duplicate_active_lease_returns_409(
    lease_environment,
) -> None:
    authorization_id = (
        lease_environment[
            "authorization_id"
        ]
    )

    run(
        execution_leases
        .acquire_execution_lease(
            authorization_id,
            acquire_payload(
                owner_id="worker:1"
            ),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_leases
            .acquire_execution_lease(
                authorization_id,
                acquire_payload(
                    owner_id="worker:2"
                ),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "lease_conflict"
    )


def test_unknown_authorization_returns_404(
    lease_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_leases
            .acquire_execution_lease(
                "authorization:missing",
                acquire_payload(),
            )
        )

    assert exc.value.status_code == 404


def test_renew_lease(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    renewed = run(
        execution_leases
        .renew_execution_lease(
            created["lease_id"],
            (
                execution_leases
                .RenewLeasePayload(
                    lease_token=
                        created["lease_token"],
                    expected_version=1,
                    ttl_seconds=120,
                )
            ),
        )
    )

    assert renewed["status"] == "active"
    assert renewed["lease_version"] == 2
    assert renewed["renewed_at"] is not None
    assert renewed["token_exposed"] is True


def test_wrong_token_returns_403(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_leases
            .renew_execution_lease(
                created["lease_id"],
                (
                    execution_leases
                    .RenewLeasePayload(
                        lease_token=
                            "wrong-token",
                        expected_version=1,
                        ttl_seconds=60,
                    )
                ),
            )
        )

    assert exc.value.status_code == 403

    assert (
        exc.value.detail["type"]
        == "lease_token_mismatch"
    )


def test_stale_lease_version_returns_409(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    run(
        execution_leases
        .renew_execution_lease(
            created["lease_id"],
            (
                execution_leases
                .RenewLeasePayload(
                    lease_token=
                        created["lease_token"],
                    expected_version=1,
                    ttl_seconds=60,
                )
            ),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_leases
            .renew_execution_lease(
                created["lease_id"],
                (
                    execution_leases
                    .RenewLeasePayload(
                        lease_token=
                            created[
                                "lease_token"
                            ],
                        expected_version=1,
                        ttl_seconds=60,
                    )
                ),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "lease_version_conflict"
    )

    assert (
        exc.value.detail["actual_version"]
        == 2
    )


def test_release_lease(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    released = run(
        execution_leases
        .release_execution_lease(
            created["lease_id"],
            (
                execution_leases
                .ReleaseLeasePayload(
                    lease_token=
                        created["lease_token"],
                    expected_version=1,
                )
            ),
        )
    )

    assert released["status"] == "released"
    assert released["lease_version"] == 2
    assert released["released_at"] is not None
    assert released["is_active"] is False


def test_verify_token(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    valid = run(
        execution_leases
        .verify_execution_lease(
            created["lease_id"],
            (
                execution_leases
                .VerifyLeasePayload(
                    lease_token=
                        created["lease_token"]
                )
            ),
        )
    )

    invalid = run(
        execution_leases
        .verify_execution_lease(
            created["lease_id"],
            (
                execution_leases
                .VerifyLeasePayload(
                    lease_token=
                        "wrong-token"
                )
            ),
        )
    )

    assert valid["token_valid"] is True
    assert invalid["token_valid"] is False


def test_lease_events(
    lease_environment,
) -> None:
    created = run(
        execution_leases
        .acquire_execution_lease(
            lease_environment[
                "authorization_id"
            ],
            acquire_payload(),
        )
    )

    renewed = run(
        execution_leases
        .renew_execution_lease(
            created["lease_id"],
            (
                execution_leases
                .RenewLeasePayload(
                    lease_token=
                        created["lease_token"],
                    expected_version=1,
                    ttl_seconds=60,
                )
            ),
        )
    )

    run(
        execution_leases
        .release_execution_lease(
            renewed["lease_id"],
            (
                execution_leases
                .ReleaseLeasePayload(
                    lease_token=
                        renewed["lease_token"],
                    expected_version=2,
                )
            ),
        )
    )

    result = run(
        execution_leases
        .execution_lease_events(
            created["lease_id"]
        )
    )

    assert [
        event["event_type"]
        for event in result["events"]
    ] == [
        "acquired",
        "renewed",
        "released",
    ]


def test_missing_lease_returns_404(
    lease_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_leases
            .get_execution_lease(
                "lease:missing"
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
            "/api/v1/"
            "execution-authorizations/"
            "{authorization_id}/lease"
        ),
        "/api/v1/execution-leases",
        (
            "/api/v1/"
            "execution-leases/{lease_id}"
        ),
        (
            "/api/v1/"
            "execution-leases/"
            "{lease_id}/renew"
        ),
        (
            "/api/v1/"
            "execution-leases/"
            "{lease_id}/release"
        ),
        (
            "/api/v1/"
            "execution-leases/"
            "{lease_id}/events"
        ),
        (
            "/api/v1/"
            "execution-leases/"
            "{lease_id}/verify"
        ),
    }

    assert expected.issubset(
        paths
    )
