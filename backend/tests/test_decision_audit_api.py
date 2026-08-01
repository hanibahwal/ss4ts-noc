from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import decision_audits
from app.api.v1.router import api_router
from app.services.decision_audit_store import (
    DecisionAuditStore,
)
from tests.test_decision_fusion import (
    make_graph,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


@pytest.fixture
def audit_environment(
    tmp_path,
    monkeypatch,
):
    database = tmp_path / "audit-api.db"

    monkeypatch.setenv(
        "SS4TS_DECISION_AUDIT_DB",
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
        decision_audits,
        "build_runtime_graph",
        fake_graph,
    )

    return database


def test_create_audit(
    audit_environment,
) -> None:
    result = run(
        decision_audits
        .create_decision_audit(
            "device:core",
            max_depth=10,
            refresh=False,
        )
    )

    assert result["audit_id"]
    assert result["verified"] is True

    assert (
        result["primary_cause_id"]
        .startswith("cause:power:")
    )

    assert (
        result["safety"]
        ["device_command_executed"]
        is False
    )


def test_list_audits(
    audit_environment,
) -> None:
    run(
        decision_audits
        .create_decision_audit(
            "device:core",
            max_depth=10,
            refresh=False,
        )
    )

    result = run(
        decision_audits
        .list_decision_audits(
            source_node_id=
                "device:core",
            limit=100,
            offset=0,
        )
    )

    assert result["count"] == 1
    assert result["total"] == 1

    assert (
        result["records"][0]
        ["source_node_id"]
        == "device:core"
    )


def test_get_audit(
    audit_environment,
) -> None:
    created = run(
        decision_audits
        .create_decision_audit(
            "device:core",
            max_depth=10,
            refresh=False,
        )
    )

    loaded = run(
        decision_audits
        .get_decision_audit(
            created["audit_id"]
        )
    )

    assert (
        loaded["audit_id"]
        == created["audit_id"]
    )

    assert loaded["verified"] is True
    assert loaded["trace_payload"]


def test_verify_audit(
    audit_environment,
) -> None:
    created = run(
        decision_audits
        .create_decision_audit(
            "device:core",
            max_depth=10,
            refresh=False,
        )
    )

    result = run(
        decision_audits
        .verify_decision_audit(
            created["audit_id"]
        )
    )

    assert result["verified"] is True

    assert (
        result["integrity_status"]
        == "valid"
    )


def test_tampered_audit_reports_corruption(
    audit_environment,
) -> None:
    created = run(
        decision_audits
        .create_decision_audit(
            "device:core",
            max_depth=10,
            refresh=False,
        )
    )

    store = DecisionAuditStore(
        audit_environment
    )

    import sqlite3

    with sqlite3.connect(
        audit_environment
    ) as connection:
        connection.execute(
            """
            UPDATE decision_audit_records
            SET trace_payload = ?
            WHERE audit_id = ?
            """,
            (
                '{"tampered":true}',
                created["audit_id"],
            ),
        )

        connection.commit()

    assert store.verify(
        created["audit_id"]
    ) is False

    result = run(
        decision_audits
        .verify_decision_audit(
            created["audit_id"]
        )
    )

    assert result["verified"] is False

    assert (
        result["integrity_status"]
        == "corrupted"
    )


def test_missing_audit_returns_404(
    audit_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            decision_audits
            .get_decision_audit(
                "audit:missing"
            )
        )

    assert exc.value.status_code == 404


def test_unknown_node_returns_404(
    audit_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            decision_audits
            .create_decision_audit(
                "device:missing",
                max_depth=10,
                refresh=False,
            )
        )

    assert exc.value.status_code == 404


def test_audit_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/knowledge-graph/"
        "nodes/{node_id}/decision/audit"
        in paths
    )

    assert (
        "/api/v1/decision-audits"
        in paths
    )

    assert (
        "/api/v1/decision-audits/{audit_id}"
        in paths
    )

    assert (
        "/api/v1/decision-audits/"
        "{audit_id}/verify"
        in paths
    )
