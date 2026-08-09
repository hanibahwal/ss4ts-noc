from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import autonomous_shadow
from app.api.v1.router import api_router
from app.services.autonomous_shadow_mode import (
    AutonomousShadowMode,
)
from app.services.shadow_decision_store import (
    ShadowDecisionStore,
)
from app.services.decision_audit_store import (
    DecisionAuditStore,
)


def run(coroutine):
    return asyncio.run(coroutine)


def build_store(tmp_path):
    return ShadowDecisionStore(
        tmp_path / "shadow-api.db"
    )


def seed_record(store):
    service = AutonomousShadowMode(store)

    return service.record_decision(
        decision={
            "decision_id": "decision-api-1",
            "action": "SAFE_OPTIMIZATION",
            "risk_level": "LOW",
        },
        simulation={
            "safe_to_execute": True,
            "simulation_status": "PASSED",
            "confidence": 95,
        },
        source_node_id="router-api-1",
        predicted_outcome={
            "expected_action_status":
                "completed",
            "expected_simulation_status":
                "completed",
            "expected_lease_status":
                "released",
            "expected_rollback_performed":
                False,
            "expected_failed_step_id":
                None,
            "proposed_action":
                "SAFE_OPTIMIZATION",
            "dry_run_only":
                True,
        },
    )


def seed_evidence(
    store,
    *,
    decision_id,
    source_node_id="router-api-1",
):
    return store.create_record(
        trace={
            "trace_id":
                "trace:shadow-outcome",
            "decision_id":
                decision_id,
            "source_node_id":
                source_node_id,
            "final_outcome": {
                "action_status":
                    "completed",
                "authorization_status":
                    "consumed",
                "simulation_status":
                    "completed",
                "lease_status":
                    "released",
            },
        },
        explanation={
            "execution_safety": {
                "dry_run_only": True,
            },
        },
        execution_plan={
            "decision_id":
                decision_id,
            "source_node_id":
                source_node_id,
            "dry_run_only":
                True,
        },
        simulation={
            "verification_summary": {
                "simulation_completed":
                    True,
                "rollback_performed":
                    False,
                "failed_step_id":
                    None,
                "final_action_status":
                    "completed",
                "lease_released":
                    True,
            },
        },
        metadata={
            "evidence_bundle": True,
            "created_by":
                "h32.3-api-test",
        },
    )


def test_router_is_registered():
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/autonomous-shadow"
        in paths
    )

    assert (
        "/api/v1/autonomous-shadow/"
        "{shadow_id}"
        in paths
    )


def test_list_shadow_decisions(
    tmp_path,
    monkeypatch,
):
    store = build_store(tmp_path)
    seed_record(store)

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: store,
    )

    result = run(
        autonomous_shadow
        .list_shadow_decisions(
            limit=100
        )
    )

    assert result["count"] == 1

    record = result["records"][0]

    assert (
        record["decision_id"]
        == "decision-api-1"
    )
    assert record["dry_run_only"] is True

    assert (
        result["safety"][
            "execution_enabled"
        ]
        is False
    )
    assert (
        result["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_get_shadow_decision(
    tmp_path,
    monkeypatch,
):
    store = build_store(tmp_path)
    record = seed_record(store)

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: store,
    )

    result = run(
        autonomous_shadow
        .get_shadow_decision(
            record.shadow_id
        )
    )

    assert (
        result["shadow_id"]
        == record.shadow_id
    )

    assert (
        result["safety"][
            "execution_authority"
        ]
        is False
    )

    assert (
        result["safety"][
            "network_io_performed"
        ]
        is False
    )


def test_missing_shadow_returns_404(
    tmp_path,
    monkeypatch,
):
    store = build_store(tmp_path)

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: store,
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        run(
            autonomous_shadow
            .get_shadow_decision(
                "shadow:missing"
            )
        )

    assert exc_info.value.status_code == 404


def test_api_has_no_execution_routes():
    shadow_routes = [
        route
        for route in api_router.routes
        if route.path.startswith(
            "/api/v1/autonomous-shadow"
        )
    ]

    methods = {
        method
        for route in shadow_routes
        for method in getattr(
            route,
            "methods",
            set(),
        )
    }

    assert methods == {"GET"}


def test_outcome_comparison_endpoint(
    tmp_path,
    monkeypatch,
):
    shadow_store = build_store(
        tmp_path
    )

    shadow = seed_record(
        shadow_store
    )

    audit_store = DecisionAuditStore(
        tmp_path / "outcome-audit.db"
    )

    seed_evidence(
        audit_store,
        decision_id=
            shadow.decision_id,
        source_node_id=
            shadow.source_node_id,
    )

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: shadow_store,
    )

    monkeypatch.setattr(
        autonomous_shadow,
        "get_audit_store",
        lambda: audit_store,
    )

    result = run(
        autonomous_shadow
        .get_shadow_outcome_comparison(
            shadow.shadow_id
        )
    )

    assert result["evidence_verified"] is True
    assert result["overall_match"] is True
    assert result["accuracy_percent"] == 100.0

    assert (
        result["safety"]["read_only"]
        is True
    )

    assert (
        result["safety"][
            "execution_authority"
        ]
        is False
    )

    assert (
        result["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_outcome_comparison_missing_evidence_404(
    tmp_path,
    monkeypatch,
):
    shadow_store = build_store(
        tmp_path
    )

    shadow = seed_record(
        shadow_store
    )

    audit_store = DecisionAuditStore(
        tmp_path / "empty-audit.db"
    )

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: shadow_store,
    )

    monkeypatch.setattr(
        autonomous_shadow,
        "get_audit_store",
        lambda: audit_store,
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        run(
            autonomous_shadow
            .get_shadow_outcome_comparison(
                shadow.shadow_id
            )
        )

    assert (
        exc_info.value.status_code
        == 404
    )


def test_shadow_api_remains_get_only():
    routes = [
        route
        for route in api_router.routes
        if route.path.startswith(
            "/api/v1/autonomous-shadow"
        )
    ]

    assert routes

    for route in routes:
        assert (
            route.methods
            == {"GET"}
        )
