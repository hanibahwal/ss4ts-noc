from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.models.autonomous_controlled_authorization_approval_candidate import (
    AutonomousControlledAuthorizationApprovalCandidate,
)
from app.services.autonomous_execution_authorization_binding_audit import (
    verify_autonomous_execution_authorization_binding_store,
)
from app.services.autonomous_execution_authorization_binding_store import (
    AutonomousExecutionAuthorizationBindingStore,
    calculate_binding_record_hash,
)
from tests.test_autonomous_execution_authorization_binding_service import (
    NOW,
)
from tests.test_autonomous_execution_authorization_binding_store import (
    make_binding,
)


def make_verified_sources(
    tmp_path,
):
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    binding_record = store.append(
        binding=make_binding(
            tmp_path / "binding",
            suffix="approval-candidate",
        ),
        stored_at=NOW,
    )

    binding_audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    return binding_record, binding_audit


def make_candidate(
    tmp_path,
):
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    return (
        AutonomousControlledAuthorizationApprovalCandidate
        .from_verified_binding(
            approval_candidate_id=(
                "approval-candidate:h25:1"
            ),
            binding_record=binding_record,
            binding_audit=binding_audit,
            requested_by="operator:hani",
            approval_reason=(
                "Human approval required before "
                "controlled execution"
            ),
            requested_at=NOW,
            expires_at=(
                NOW
                + timedelta(
                    minutes=30
                )
            ),
        )
    )


def test_create_candidate_from_verified_binding(
    tmp_path,
) -> None:
    candidate = make_candidate(
        tmp_path
    )

    assert (
        candidate.approval_candidate_id
        == "approval-candidate:h25:1"
    )

    assert candidate.binding_audit_valid is True

    assert (
        candidate.authorization_status
        == "pending"
    )

    assert (
        candidate.authorization_decision
        == "require_approval"
    )

    assert (
        candidate.candidate_fingerprint
        == candidate.calculate_fingerprint()
    )


def test_candidate_is_immutable(
    tmp_path,
) -> None:
    candidate = make_candidate(
        tmp_path
    )

    with pytest.raises(
        AttributeError,
    ):
        candidate.requested_by = "changed"


def test_candidate_is_never_executable(
    tmp_path,
) -> None:
    candidate = make_candidate(
        tmp_path
    )

    payload = candidate.to_dict()

    assert (
        candidate.approval_candidate_created
        is True
    )
    assert candidate.authorization_approved is False
    assert (
        candidate.authorization_token_created
        is False
    )
    assert candidate.approval_claim_created is False
    assert candidate.execution_lease_created is False
    assert candidate.execution_allowed is False
    assert candidate.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["approval_candidate_only"]
        is True
    )

    assert (
        payload["safety"]["human_approval_required"]
        is True
    )


def test_invalid_binding_audit_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    invalid_audit = replace(
        binding_audit,
        record_hashes_valid=False,
    )

    with pytest.raises(
        ValueError,
        match="audit is invalid",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:invalid-audit"
                ),
                binding_record=binding_record,
                binding_audit=invalid_audit,
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )


def test_tampered_binding_record_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    tampered_record = replace(
        binding_record,
        record_hash="f" * 64,
    )

    with pytest.raises(
        ValueError,
        match="record hash is invalid",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:tampered"
                ),
                binding_record=tampered_record,
                binding_audit=binding_audit,
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )


def test_unsafe_binding_claim_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    payload = deepcopy(
        binding_record.binding_payload
    )

    payload["can_execute"] = True

    unsafe_record_hash = (
        calculate_binding_record_hash(
            sequence_number=(
                binding_record.sequence_number
            ),
            binding_id=(
                binding_record.binding_id
            ),
            authorization_intent_id=(
                binding_record.authorization_intent_id
            ),
            intent_record_hash=(
                binding_record.intent_record_hash
            ),
            intent_bridge_fingerprint=(
                binding_record.intent_bridge_fingerprint
            ),
            intent_audit_id=(
                binding_record.intent_audit_id
            ),
            execution_authorization_id=(
                binding_record.execution_authorization_id
            ),
            plan_id=(
                binding_record.plan_id
            ),
            decision_id=(
                binding_record.decision_id
            ),
            risk_class=(
                binding_record.risk_class
            ),
            authorization_status=(
                binding_record.authorization_status
            ),
            authorization_decision=(
                binding_record.authorization_decision
            ),
            binding_fingerprint=(
                binding_record.binding_fingerprint
            ),
            binding_payload=payload,
            stored_at=(
                binding_record.stored_at
            ),
            previous_record_hash=(
                binding_record.previous_record_hash
            ),
        )
    )

    unsafe_record = replace(
        binding_record,
        binding_payload=payload,
        record_hash=unsafe_record_hash,
    )

    assert unsafe_record.verify_hash() is True

    with pytest.raises(
        ValueError,
        match="unsafe claim",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:unsafe"
                ),
                binding_record=unsafe_record,
                binding_audit=binding_audit,
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )


def test_empty_requested_by_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="requested_by",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:no-requester"
                ),
                binding_record=binding_record,
                binding_audit=binding_audit,
                requested_by=" ",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )


def test_empty_approval_reason_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="approval_reason",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:no-reason"
                ),
                binding_record=binding_record,
                binding_audit=binding_audit,
                requested_by="operator:hani",
                approval_reason=" ",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )


def test_naive_requested_at_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="requested_at must be timezone-aware",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:naive-time"
                ),
                binding_record=binding_record,
                binding_audit=binding_audit,
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=datetime(
                    2026,
                    8,
                    6,
                    22,
                    30,
                ),
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )


def test_expiry_must_follow_request_time(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="later than requested_at",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id=(
                    "approval-candidate:expired"
                ),
                binding_record=binding_record,
                binding_audit=binding_audit,
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=NOW,
            )
        )


def test_candidate_fingerprint_mismatch_rejected(
    tmp_path,
) -> None:
    candidate = make_candidate(
        tmp_path
    )

    values = {
        field_name:
            getattr(
                candidate,
                field_name,
            )
        for field_name in (
            "approval_candidate_id",
            "binding_id",
            "binding_record_hash",
            "binding_fingerprint",
            "binding_audit_id",
            "binding_audit_valid",
            "authorization_intent_id",
            "execution_authorization_id",
            "plan_id",
            "decision_id",
            "risk_class",
            "authorization_status",
            "authorization_decision",
            "requested_by",
            "approval_reason",
            "requested_at",
            "expires_at",
        )
    }

    with pytest.raises(
        ValueError,
        match="candidate_fingerprint mismatch",
    ):
        AutonomousControlledAuthorizationApprovalCandidate(
            **values,
            candidate_fingerprint="f" * 64,
        )


def test_invalid_source_types_rejected(
    tmp_path,
) -> None:
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    with pytest.raises(
        TypeError,
        match="binding_record",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id="candidate:invalid",
                binding_record="invalid",
                binding_audit=binding_audit,
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )

    with pytest.raises(
        TypeError,
        match="binding_audit",
    ):
        (
            AutonomousControlledAuthorizationApprovalCandidate
            .from_verified_binding(
                approval_candidate_id="candidate:invalid",
                binding_record=binding_record,
                binding_audit="invalid",
                requested_by="operator:hani",
                approval_reason="Approval required",
                requested_at=NOW,
                expires_at=(
                    NOW
                    + timedelta(
                        minutes=30
                    )
                ),
            )
        )
