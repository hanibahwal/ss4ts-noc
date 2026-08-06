from __future__ import annotations

import sqlite3

import pytest

from app.models.autonomous_operation_proposal import (
    AutonomousOperationMode,
    AutonomousOperationProposal,
    AutonomousPolicyStatus,
    AutonomousProposalRiskLevel,
)
from app.services.autonomous_proposal_audit import (
    AutonomousProposalAuditVerifier,
    verify_autonomous_proposal_store,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBindingResult,
)
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicyResult,
)
from app.services.autonomous_proposal_store import (
    AutonomousProposalStore,
)


def make_proposal(
    proposal_id: str,
    source_signal_id: str,
) -> AutonomousOperationProposal:
    return AutonomousOperationProposal(
        proposal_id=proposal_id,
        source_signal_id=source_signal_id,
        decision_id=(
            f"decision:{proposal_id}"
        ),
        plan_id=(
            f"plan:{proposal_id}"
        ),
        target_node_id="device:router-01",
        operation_type="disable_interface",
        summary="Review interface action",
        reason="Interface instability",
        confidence_percent=93,
        risk_level=(
            AutonomousProposalRiskLevel.HIGH
        ),
        policy_status=(
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
        ),
        operating_mode=(
            AutonomousOperationMode
            .APPROVAL_CANDIDATE
        ),
        requires_human_approval=True,
    )


def make_policy(
    proposal_id: str,
) -> AutonomousProposalPolicyResult:
    return AutonomousProposalPolicyResult(
        proposal_id=proposal_id,
        policy_status=(
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
        ),
        operating_mode=(
            AutonomousOperationMode
            .APPROVAL_CANDIDATE
        ),
        requires_human_approval=True,
        allowed_for_review=True,
        blocked=False,
        reasons=(
            "Human approval required",
        ),
        confidence_threshold=70,
        evaluated_confidence=93,
    )


def make_binding(
    proposal_id: str,
) -> AutonomousProposalBindingResult:
    return AutonomousProposalBindingResult(
        proposal_id=proposal_id,
        decision_id=(
            f"decision:{proposal_id}"
        ),
        plan_id=(
            f"plan:{proposal_id}"
        ),
        binding_valid=True,
        binding_errors=(),
        decision_consistent=True,
        plan_consistent=True,
        target_consistent=True,
        operation_consistent=True,
        confidence_consistent=True,
        risk_consistent=True,
        policy_review_allowed=True,
        proposal_not_expired=True,
        human_approval_required=True,
        dry_run_only=True,
    )


def append_record(
    store: AutonomousProposalStore,
    number: int,
) -> None:
    proposal_id = (
        f"proposal:audit-{number}"
    )

    store.append(
        proposal=make_proposal(
            proposal_id,
            f"signal:audit-{number}",
        ),
        policy=make_policy(
            proposal_id
        ),
        binding=make_binding(
            proposal_id
        ),
    )


def test_valid_ledger_passes_audit(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_record(
        store,
        1,
    )

    append_record(
        store,
        2,
    )

    report = (
        verify_autonomous_proposal_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 2
    assert report.verified_record_count == 2
    assert report.first_sequence == 1
    assert report.last_sequence == 2
    assert report.errors == ()


def test_empty_ledger_is_valid_with_warning(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    report = (
        verify_autonomous_proposal_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 0
    assert report.warnings == (
        "Autonomous proposal ledger is empty",
    )


def test_missing_database_is_reported(
    tmp_path,
) -> None:
    report = AutonomousProposalAuditVerifier(
        tmp_path / "missing.db"
    ).verify()

    assert report.audit_valid is False
    assert report.record_count == 0

    assert (
        "does not exist"
        in report.errors[0]
    )


def test_tampered_payload_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    append_record(
        store,
        1,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET proposal_payload = ?
            WHERE sequence_number = 1
            """,
            (
                '{"tampered":true}',
            ),
        )

        connection.commit()

    report = AutonomousProposalAuditVerifier(
        database
    ).verify()

    assert report.audit_valid is False
    assert report.hashes_valid is False

    assert any(
        "Record hash mismatch"
        in error
        for error in report.errors
    )


def test_invalid_json_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    append_record(
        store,
        1,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET policy_payload = ?
            WHERE sequence_number = 1
            """,
            (
                "{invalid-json",
            ),
        )

        connection.commit()

    report = AutonomousProposalAuditVerifier(
        database
    ).verify()

    assert report.audit_valid is False
    assert report.payloads_valid is False

    assert any(
        "Invalid stored payload"
        in error
        for error in report.errors
    )


def test_broken_chain_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    append_record(
        store,
        1,
    )

    append_record(
        store,
        2,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET previous_record_hash = ?
            WHERE sequence_number = 2
            """,
            (
                "f" * 64,
            ),
        )

        connection.commit()

    report = AutonomousProposalAuditVerifier(
        database
    ).verify()

    assert report.audit_valid is False
    assert report.chain_valid is False

    assert any(
        "Hash-chain mismatch"
        in error
        for error in report.errors
    )


def test_invalid_genesis_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    append_record(
        store,
        1,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET previous_record_hash = ?
            WHERE sequence_number = 1
            """,
            (
                "a" * 64,
            ),
        )

        connection.commit()

    report = AutonomousProposalAuditVerifier(
        database
    ).verify()

    assert report.audit_valid is False
    assert report.genesis_valid is False


def test_sequence_gap_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    append_record(
        store,
        1,
    )

    append_record(
        store,
        2,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET sequence_number = 3
            WHERE sequence_number = 2
            """
        )

        connection.commit()

    report = AutonomousProposalAuditVerifier(
        database
    ).verify()

    assert report.audit_valid is False
    assert report.sequence_valid is False

    assert any(
        "Sequence mismatch"
        in error
        for error in report.errors
    )


def test_audit_report_has_no_execution_authority(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    report = (
        verify_autonomous_proposal_store(
            store
        )
    )

    payload = report.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "read_only_audit": True,
        "database_write_performed": False,
        "authorization_created": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }


def test_audit_does_not_change_database(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_record(
        store,
        1,
    )

    before = store.count()

    verify_autonomous_proposal_store(
        store
    )

    after = store.count()

    assert before == after == 1


def test_invalid_store_type_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match="AutonomousProposalStore",
    ):
        verify_autonomous_proposal_store(
            "invalid"
        )
