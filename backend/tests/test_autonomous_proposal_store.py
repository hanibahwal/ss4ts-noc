from __future__ import annotations

import sqlite3

import pytest

from app.models.autonomous_operation_proposal import (
    AutonomousOperationMode,
    AutonomousOperationProposal,
    AutonomousPolicyStatus,
    AutonomousProposalRiskLevel,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBindingResult,
)
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicyResult,
)
from app.services.autonomous_proposal_store import (
    AutonomousProposalDuplicate,
    AutonomousProposalIntegrityError,
    AutonomousProposalStore,
    GENESIS_RECORD_HASH,
)


def make_proposal(
    *,
    proposal_id: str = "proposal:store-1",
    source_signal_id: str = "signal:store-1",
) -> AutonomousOperationProposal:
    return AutonomousOperationProposal(
        proposal_id=proposal_id,
        source_signal_id=source_signal_id,
        decision_id="decision:store-1",
        plan_id="plan:store-1",
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
        policy_reasons=(
            "Human approval required",
        ),
    )


def make_policy(
    proposal_id: str = "proposal:store-1",
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
    proposal_id: str = "proposal:store-1",
) -> AutonomousProposalBindingResult:
    return AutonomousProposalBindingResult(
        proposal_id=proposal_id,
        decision_id="decision:store-1",
        plan_id="plan:store-1",
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


def test_append_and_get_record(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    record = store.append(
        proposal=make_proposal(),
        policy=make_policy(),
        binding=make_binding(),
    )

    loaded = store.get(
        "proposal:store-1"
    )

    assert loaded == record
    assert loaded is not None
    assert loaded.verify_hash() is True
    assert loaded.can_execute is False
    assert store.count() == 1


def test_first_record_uses_genesis_hash(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    record = store.append(
        proposal=make_proposal(),
        policy=make_policy(),
        binding=make_binding(),
    )

    assert record.sequence_number == 1

    assert (
        record.previous_record_hash
        == GENESIS_RECORD_HASH
    )


def test_records_form_hash_chain(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    first = store.append(
        proposal=make_proposal(),
        policy=make_policy(),
        binding=make_binding(),
    )

    second_id = "proposal:store-2"

    second = store.append(
        proposal=make_proposal(
            proposal_id=second_id,
            source_signal_id="signal:store-2",
        ),
        policy=make_policy(
            second_id
        ),
        binding=make_binding(
            second_id
        ),
    )

    assert second.sequence_number == 2

    assert (
        second.previous_record_hash
        == first.record_hash
    )

    assert store.verify_chain() is True


def test_duplicate_proposal_id_is_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    proposal = make_proposal()

    store.append(
        proposal=proposal,
        policy=make_policy(),
        binding=make_binding(),
    )

    with pytest.raises(
        AutonomousProposalDuplicate,
    ):
        store.append(
            proposal=proposal,
            policy=make_policy(),
            binding=make_binding(),
        )


def test_duplicate_fingerprint_is_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    first = make_proposal()

    store.append(
        proposal=first,
        policy=make_policy(),
        binding=make_binding(),
    )

    second = make_proposal(
        proposal_id="proposal:store-2"
    )

    second.proposal_id = (
        "proposal:store-2"
    )

    with pytest.raises(
        AutonomousProposalDuplicate,
    ):
        store.append(
            proposal=second,
            policy=make_policy(
                "proposal:store-2"
            ),
            binding=make_binding(
                "proposal:store-2"
            ),
        )


def test_tampered_payload_is_detected(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    store.append(
        proposal=make_proposal(),
        policy=make_policy(),
        binding=make_binding(),
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET proposal_payload = ?
            WHERE proposal_id = ?
            """,
            (
                '{"tampered":true}',
                "proposal:store-1",
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousProposalIntegrityError,
        match="hash mismatch",
    ):
        store.get(
            "proposal:store-1"
        )


def test_broken_previous_hash_is_detected(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    store.append(
        proposal=make_proposal(),
        policy=make_policy(),
        binding=make_binding(),
    )

    second_id = "proposal:store-2"

    store.append(
        proposal=make_proposal(
            proposal_id=second_id,
            source_signal_id="signal:store-2",
        ),
        policy=make_policy(
            second_id
        ),
        binding=make_binding(
            second_id
        ),
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET previous_record_hash = ?
            WHERE proposal_id = ?
            """,
            (
                "f" * 64,
                second_id,
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousProposalIntegrityError,
    ):
        store.verify_chain()


def test_mismatched_policy_proposal_is_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    with pytest.raises(
        ValueError,
        match="Policy result proposal ID",
    ):
        store.append(
            proposal=make_proposal(),
            policy=make_policy(
                "proposal:different"
            ),
            binding=make_binding(),
        )


def test_mismatched_binding_proposal_is_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    with pytest.raises(
        ValueError,
        match="Binding result proposal ID",
    ):
        store.append(
            proposal=make_proposal(),
            policy=make_policy(),
            binding=make_binding(
                "proposal:different"
            ),
        )


def test_record_safety_evidence(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    record = store.append(
        proposal=make_proposal(),
        policy=make_policy(),
        binding=make_binding(),
    )

    payload = record.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "immutable_record": True,
        "append_only": True,
        "execution_authority": False,
        "authorization_created": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }


@pytest.mark.parametrize(
    (
        "argument",
        "value",
        "message",
    ),
    [
        (
            "proposal",
            "invalid",
            "AutonomousOperationProposal",
        ),
        (
            "policy",
            "invalid",
            "AutonomousProposalPolicyResult",
        ),
        (
            "binding",
            "invalid",
            "AutonomousProposalBindingResult",
        ),
    ],
)
def test_invalid_input_types_are_rejected(
    tmp_path,
    argument,
    value,
    message,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    arguments = {
        "proposal": make_proposal(),
        "policy": make_policy(),
        "binding": make_binding(),
    }

    arguments[argument] = value

    with pytest.raises(
        TypeError,
        match=message,
    ):
        store.append(
            **arguments
        )


def test_unknown_proposal_returns_none(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    assert (
        store.get(
            "proposal:missing"
        )
        is None
    )


def test_list_records_is_sequence_ordered(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    for number in range(
        1,
        4,
    ):
        proposal_id = (
            f"proposal:store-{number}"
        )

        store.append(
            proposal=make_proposal(
                proposal_id=proposal_id,
                source_signal_id=(
                    f"signal:store-{number}"
                ),
            ),
            policy=make_policy(
                proposal_id
            ),
            binding=make_binding(
                proposal_id
            ),
        )

    records = store.list_records()

    assert [
        record.sequence_number
        for record in records
    ] == [1, 2, 3]
