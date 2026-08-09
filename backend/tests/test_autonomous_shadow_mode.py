from app.services.autonomous_shadow_mode import (
    AutonomousShadowMode,
)
from app.services.shadow_decision_store import (
    ShadowDecisionStore,
)


def build_service(tmp_path):
    store = ShadowDecisionStore(
        tmp_path / "shadow.db"
    )
    return AutonomousShadowMode(store), store


def test_shadow_decision_is_persisted(
    tmp_path,
):
    service, store = build_service(tmp_path)

    record = service.record_decision(
        decision={
            "decision_id": "decision-1",
            "action": "SAFE_OPTIMIZATION",
            "risk_level": "LOW",
        },
        simulation={
            "safe_to_execute": True,
            "simulation_status": "PASSED",
            "confidence": 91,
        },
        source_node_id="172.22.1.25",
    )

    stored = store.get(record.shadow_id)

    assert stored is not None
    assert stored.decision_id == "decision-1"
    assert stored.dry_run_only is True


def test_shadow_mode_never_grants_execution(
    tmp_path,
):
    service, _ = build_service(tmp_path)

    record = service.record_decision(
        decision={
            "decision_id": "decision-2",
            "action": "SAFE_OPTIMIZATION",
        },
        simulation={
            "safe_to_execute": True,
            "simulation_status": "PASSED",
            "confidence": 99,
        },
        source_node_id="router-1",
    )

    assert (
        record.metadata["execution_enabled"]
        is False
    )
    assert (
        record.metadata["execution_authority"]
        is False
    )
    assert (
        record.metadata["network_io_performed"]
        is False
    )
    assert (
        record.metadata["device_command_executed"]
        is False
    )


def test_shadow_mode_records_blocked_simulation(
    tmp_path,
):
    service, _ = build_service(tmp_path)

    record = service.record_decision(
        decision={
            "decision_id": "decision-3",
            "action": "CHANGE_ROUTE",
            "risk_level": "HIGH",
        },
        simulation={
            "safe_to_execute": False,
            "simulation_status": "BLOCKED",
            "confidence": 40,
            "reason": "Approval required",
        },
        source_node_id="router-2",
    )

    assert (
        record.simulation_status
        == "BLOCKED"
    )
    assert (
        record.predicted_outcome[
            "safe_to_execute"
        ]
        is False
    )


def test_missing_decision_id_is_rejected(
    tmp_path,
):
    import pytest

    service, _ = build_service(tmp_path)

    with pytest.raises(ValueError):
        service.record_decision(
            decision={
                "action": "SAFE_OPTIMIZATION",
            },
            simulation={},
            source_node_id="router-1",
        )


def test_invalid_confidence_is_rejected(
    tmp_path,
):
    import pytest

    service, _ = build_service(tmp_path)

    with pytest.raises(ValueError):
        service.record_decision(
            decision={
                "decision_id": "decision-4",
            },
            simulation={
                "confidence": 120,
            },
            source_node_id="router-1",
        )


def test_recent_shadow_records(
    tmp_path,
):
    service, store = build_service(tmp_path)

    for index in range(3):
        service.record_decision(
            decision={
                "decision_id":
                    f"decision-{index}",
                "action":
                    "SAFE_OPTIMIZATION",
            },
            simulation={
                "confidence": 80,
            },
            source_node_id="router-1",
        )

    records = store.list_recent(limit=10)

    assert len(records) == 3
