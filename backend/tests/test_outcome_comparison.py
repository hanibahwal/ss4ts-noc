from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.decision_audit import (
    DecisionAuditRecord,
)
from app.models.shadow_decision import (
    ShadowDecisionRecord,
)
from app.services.outcome_comparison import (
    compare_shadow_to_evidence,
)


def make_shadow():
    return ShadowDecisionRecord(
        shadow_id="shadow:test",
        decision_id="decision:test",
        source_node_id="device:test",
        proposed_action="disable_interface",
        confidence_percent=95,
        risk_level="HIGH",
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
            "dry_run_only":
                True,
        },
        simulation_status="COMPLETED",
        dry_run_only=True,
        created_at=datetime.now(
            timezone.utc
        ),
        metadata={
            "shadow_mode": True,
        },
    )


def make_audit(
    *,
    action_status="completed",
    simulation_status="completed",
    lease_status="released",
    rollback_performed=False,
    failed_step_id=None,
):
    return DecisionAuditRecord(
        audit_id="audit:test",
        trace_id="trace:test",
        decision_id="decision:test",
        source_node_id="device:test",
        trace_payload={
            "final_outcome": {
                "action_status":
                    action_status,
                "simulation_status":
                    simulation_status,
                "lease_status":
                    lease_status,
            },
        },
        execution_plan_payload={
            "dry_run_only": True,
        },
        simulation_payload={
            "verification_summary": {
                "rollback_performed":
                    rollback_performed,
                "failed_step_id":
                    failed_step_id,
            },
        },
        checksum="a" * 64,
    )


def test_full_match():
    result = compare_shadow_to_evidence(
        shadow=make_shadow(),
        audit=make_audit(),
    )

    assert result.overall_match is True
    assert result.matched_fields == 6
    assert result.mismatched_fields == 0
    assert result.accuracy_percent == 100.0


def test_failed_outcome_detects_mismatch():
    result = compare_shadow_to_evidence(
        shadow=make_shadow(),
        audit=make_audit(
            action_status="failed",
            simulation_status="failed",
            rollback_performed=True,
            failed_step_id="step:1",
        ),
    )

    assert result.overall_match is False
    assert result.accuracy_percent < 100
    assert (
        result.field_results[
            "action_status"
        ]
        is False
    )
    assert (
        result.field_results[
            "simulation_status"
        ]
        is False
    )


def test_decision_mismatch_rejected():
    audit = make_audit()
    audit.decision_id = "decision:other"

    with pytest.raises(ValueError):
        compare_shadow_to_evidence(
            shadow=make_shadow(),
            audit=audit,
        )


def test_result_is_read_only():
    result = compare_shadow_to_evidence(
        shadow=make_shadow(),
        audit=make_audit(),
    ).to_dict()

    safety = result["safety"]

    assert safety["read_only"] is True
    assert (
        safety["execution_enabled"]
        is False
    )
    assert (
        safety["execution_authority"]
        is False
    )
    assert (
        safety["network_io_performed"]
        is False
    )
    assert (
        safety["device_command_executed"]
        is False
    )
