from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.models.autonomous_authorization_request import (
    AutonomousControlledAuthorizationRequest,
)
from app.models.execution_authorization import (
    ExecutionRiskClass,
)
from app.services.autonomous_authorization_candidate_audit import (
    verify_autonomous_authorization_candidate_store,
)
from app.services.autonomous_authorization_candidate_store import (
    AutonomousAuthorizationCandidateStore,
)
from app.services.autonomous_authorization_request import (
    create_autonomous_authorization_request,
)
from tests.test_autonomous_authorization_candidate_store import (
    make_candidate,
)


NOW = datetime(
    2026,
    8,
    6,
    20,
    20,
    tzinfo=timezone.utc,
)


def make_context(
    tmp_path,
):
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    record = store.append(
        candidate=make_candidate(
            tmp_path,
            number=1,
        )
    )

    audit = (
        verify_autonomous_authorization_candidate_store(
            store
        )
    )

    return store, record, audit


def create_request(
    tmp_path,
):
    _, record, audit = make_context(
        tmp_path
    )

    return create_autonomous_authorization_request(
        candidate_record=record,
        candidate_audit=audit,
        requester_id="engineer:hani",
        request_reason=(
            "Submit the verified candidate "
            "for controlled authorization review"
        ),
        risk_class=ExecutionRiskClass.HIGH,
        dry_run_required=True,
        rollback_required=True,
        verification_required=True,
        requested_at=NOW,
        authorization_request_id=(
            "autonomous-authorization-request:test"
        ),
    )


def test_create_controlled_authorization_request(
    tmp_path,
) -> None:
    request = create_request(
        tmp_path
    )

    assert isinstance(
        request,
        AutonomousControlledAuthorizationRequest,
    )

    assert (
        request.authorization_request_id
        == (
            "autonomous-authorization-request:"
            "test"
        )
    )

    assert (
        request.risk_class
        is ExecutionRiskClass.HIGH
    )

    assert (
        request.candidate_audit_valid
        is True
    )


def test_request_is_not_authorization(
    tmp_path,
) -> None:
    request = create_request(
        tmp_path
    )

    assert (
        request.authorization_request_created
        is True
    )

    assert (
        request.authorization_created
        is False
    )

    assert (
        request.authorization_approved
        is False
    )

    assert (
        request.authorization_token_created
        is False
    )

    assert (
        request.execution_lease_created
        is False
    )

    assert request.execution_allowed is False
    assert request.can_execute is False


def test_candidate_bindings_are_preserved(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    request = (
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class="medium",
            requested_at=NOW,
        )
    )

    assert (
        request.authorization_candidate_id
        == record.authorization_candidate_id
    )

    assert (
        request.candidate_record_hash
        == record.record_hash
    )

    assert (
        request.candidate_fingerprint
        == record.candidate_fingerprint
    )

    assert (
        request.review_decision_id
        == record.review_decision_id
    )

    assert (
        request.proposal_id
        == record.proposal_id
    )

    assert (
        request.candidate_audit_id
        == audit.audit_id
    )


@pytest.mark.parametrize(
    "risk_class",
    [
        ExecutionRiskClass.READ_ONLY,
        ExecutionRiskClass.LOW,
        ExecutionRiskClass.MEDIUM,
        ExecutionRiskClass.HIGH,
        ExecutionRiskClass.CRITICAL,
        "read_only",
        "low",
        "medium",
        "high",
        "critical",
    ],
)
def test_supported_risk_classes(
    tmp_path,
    risk_class,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    request = (
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class=risk_class,
            requested_at=NOW,
        )
    )

    assert (
        request.risk_class.value
        != "unknown"
    )


@pytest.mark.parametrize(
    "risk_class",
    [
        "unknown",
        "invalid",
        "",
    ],
)
def test_invalid_risk_class_rejected(
    tmp_path,
    risk_class,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="risk_class",
    ):
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class=risk_class,
        )


@pytest.mark.parametrize(
    "requester_id",
    [
        "",
        "   ",
    ],
)
def test_empty_requester_rejected(
    tmp_path,
    requester_id,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="requester_id",
    ):
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit=audit,
            requester_id=requester_id,
            request_reason="Controlled review",
            risk_class="high",
        )


@pytest.mark.parametrize(
    "request_reason",
    [
        "",
        "   ",
    ],
)
def test_empty_request_reason_rejected(
    tmp_path,
    request_reason,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="request_reason",
    ):
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason=request_reason,
            risk_class="high",
        )


def test_invalid_candidate_audit_rejected(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    invalid_audit = replace(
        audit,
        record_hashes_valid=False,
        errors=(
            "Candidate record hash mismatch",
        ),
    )

    assert invalid_audit.audit_valid is False

    with pytest.raises(
        ValueError,
        match="valid authorization candidate",
    ):
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit=invalid_audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class="high",
        )


def test_tampered_candidate_record_rejected(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    tampered = replace(
        record,
        record_hash=(
            "f" * 64
        ),
    )

    with pytest.raises(
        ValueError,
        match="record hash",
    ):
        create_autonomous_authorization_request(
            candidate_record=tampered,
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class="high",
        )


def test_tampered_candidate_fingerprint_rejected(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    payload = dict(
        record.candidate_payload
    )

    payload[
        "candidate_fingerprint"
    ] = "e" * 64

    tampered = replace(
        record,
        candidate_payload=payload,
    )

    with pytest.raises(
        ValueError,
    ):
        create_autonomous_authorization_request(
            candidate_record=tampered,
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class="high",
        )


def test_request_fingerprint_is_deterministic(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    arguments = {
        "candidate_record":
            record,
        "candidate_audit":
            audit,
        "requester_id":
            "engineer:hani",
        "request_reason":
            "Controlled authorization review",
        "risk_class":
            "critical",
        "dry_run_required":
            True,
        "rollback_required":
            True,
        "verification_required":
            True,
        "requested_at":
            NOW,
        "authorization_request_id":
            (
                "autonomous-authorization-request:"
                "deterministic"
            ),
    }

    first = (
        create_autonomous_authorization_request(
            **arguments
        )
    )

    second = (
        create_autonomous_authorization_request(
            **arguments
        )
    )

    assert (
        first.request_fingerprint
        == second.request_fingerprint
    )

    assert (
        first.calculate_fingerprint()
        == first.request_fingerprint
    )


def test_request_fingerprint_mismatch_rejected(
    tmp_path,
) -> None:
    valid = create_request(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="fingerprint mismatch",
    ):
        AutonomousControlledAuthorizationRequest(
            authorization_request_id=(
                valid.authorization_request_id
            ),
            authorization_candidate_id=(
                valid.authorization_candidate_id
            ),
            candidate_record_hash=(
                valid.candidate_record_hash
            ),
            candidate_fingerprint=(
                valid.candidate_fingerprint
            ),
            review_decision_id=(
                valid.review_decision_id
            ),
            review_record_hash=(
                valid.review_record_hash
            ),
            proposal_id=(
                valid.proposal_id
            ),
            proposal_record_hash=(
                valid.proposal_record_hash
            ),
            candidate_audit_id=(
                valid.candidate_audit_id
            ),
            candidate_audit_valid=True,
            requester_id=valid.requester_id,
            requested_at=valid.requested_at,
            request_reason=(
                valid.request_reason
            ),
            risk_class=valid.risk_class,
            dry_run_required=(
                valid.dry_run_required
            ),
            rollback_required=(
                valid.rollback_required
            ),
            verification_required=(
                valid.verification_required
            ),
            request_fingerprint=(
                "0" * 64
            ),
        )


def test_request_safety_metadata(
    tmp_path,
) -> None:
    payload = create_request(
        tmp_path
    ).to_dict()

    assert (
        payload[
            "authorization_request_created"
        ]
        is True
    )

    assert payload["can_execute"] is False
    assert payload["execution_allowed"] is False

    assert payload["safety"] == {
        "controlled_authorization_request_only": True,
        "execution_authorization_created": False,
        "authorization_approved": False,
        "authorization_token_created": False,
        "approval_claim_created": False,
        "execution_lease_created": False,
        "execution_allowed": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_access_performed": False,
        "command_generated": False,
        "device_command_executed": False,
    }


def test_invalid_candidate_record_type_rejected(
    tmp_path,
) -> None:
    _, _, audit = make_context(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match=(
            "AutonomousAuthorizationCandidateRecord"
        ),
    ):
        create_autonomous_authorization_request(
            candidate_record="invalid",
            candidate_audit=audit,
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class="high",
        )


def test_invalid_candidate_audit_type_rejected(
    tmp_path,
) -> None:
    _, record, _ = make_context(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match=(
            "AutonomousAuthorizationCandidateAuditReport"
        ),
    ):
        create_autonomous_authorization_request(
            candidate_record=record,
            candidate_audit="invalid",
            requester_id="engineer:hani",
            request_reason="Controlled review",
            risk_class="high",
        )
