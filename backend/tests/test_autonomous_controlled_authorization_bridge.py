from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.models.autonomous_authorization_intent import (
    AutonomousAuthorizationIntent,
)
from app.services.autonomous_authorization_request_audit import (
    verify_autonomous_authorization_request_store,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestStore,
)
from app.services.autonomous_controlled_authorization_bridge import (
    AutonomousControlledAuthorizationBridgeError,
    create_autonomous_authorization_intent,
)
from tests.test_autonomous_authorization_request_store import (
    make_request,
)


NOW = datetime(
    2026,
    8,
    6,
    20,
    45,
    tzinfo=timezone.utc,
)


def make_verified_inputs(
    tmp_path,
):
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    record = store.append(
        request=make_request(
            tmp_path
        )
    )

    audit = (
        verify_autonomous_authorization_request_store(
            store
        )
    )

    return record, audit


def test_create_authorization_intent(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    intent = (
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=audit,
            authorization_intent_id=(
                "autonomous-authorization-intent:test"
            ),
            created_at=NOW,
        )
    )

    assert isinstance(
        intent,
        AutonomousAuthorizationIntent,
    )

    assert (
        intent.authorization_request_id
        == record.authorization_request_id
    )

    assert (
        intent.request_record_hash
        == record.record_hash
    )

    assert (
        intent.request_audit_id
        == audit.audit_id
    )

    assert (
        intent.bridge_fingerprint
        == intent.calculate_fingerprint()
    )


def test_intent_preserves_candidate_and_proposal_bindings(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    intent = (
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        intent.authorization_candidate_id
        == record.authorization_candidate_id
    )

    assert (
        intent.candidate_record_hash
        == record.candidate_record_hash
    )

    assert (
        intent.candidate_fingerprint
        == record.candidate_fingerprint
    )

    assert (
        intent.proposal_id
        == record.proposal_id
    )

    assert (
        intent.proposal_record_hash
        == record.proposal_record_hash
    )


def test_intent_preserves_request_policy(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    intent = (
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        intent.requester_id
        == record.requester_id
    )

    assert (
        intent.requested_at
        == record.requested_at
    )

    assert (
        intent.request_reason
        == record.request_reason
    )

    assert (
        intent.risk_class.value
        == record.risk_class
    )

    assert (
        intent.dry_run_required
        == record.dry_run_required
    )

    assert (
        intent.rollback_required
        == record.rollback_required
    )

    assert (
        intent.verification_required
        == record.verification_required
    )


def test_intent_is_never_executable(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    intent = (
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        intent.authorization_request_verified
        is True
    )

    assert (
        intent.authorization_intent_created
        is True
    )

    assert (
        intent.execution_authorization_created
        is False
    )

    assert (
        intent.authorization_approved
        is False
    )

    assert (
        intent.authorization_token_created
        is False
    )

    assert (
        intent.approval_claim_created
        is False
    )

    assert (
        intent.execution_lease_created
        is False
    )

    assert (
        intent.execution_allowed
        is False
    )

    assert intent.can_execute is False


def test_intent_safety_metadata(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    payload = (
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        ).to_dict()
    )

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "authorization_intent_only": True,
        "request_store_read_only": True,
        "execution_authorization_created": False,
        "execution_authorization_stored": False,
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


def test_invalid_audit_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    invalid_audit = replace(
        audit,
        record_hashes_valid=False,
    )

    with pytest.raises(
        AutonomousControlledAuthorizationBridgeError,
        match="audit is invalid",
    ):
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=invalid_audit,
        )


def test_empty_audit_rejected(
    tmp_path,
) -> None:
    empty_store = AutonomousAuthorizationRequestStore(
        tmp_path / "empty.db"
    )

    empty_audit = (
        verify_autonomous_authorization_request_store(
            empty_store
        )
    )

    record, _ = make_verified_inputs(
        tmp_path
    )

    with pytest.raises(
        AutonomousControlledAuthorizationBridgeError,
        match="contains no records",
    ):
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=empty_audit,
        )


def test_record_outside_audit_range_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    invalid_audit = replace(
        audit,
        first_sequence_number=2,
        last_sequence_number=3,
    )

    with pytest.raises(
        AutonomousControlledAuthorizationBridgeError,
        match="outside the audited sequence range",
    ):
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=invalid_audit,
        )


def test_tampered_record_hash_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    tampered = replace(
        record,
        record_hash="f" * 64,
    )

    with pytest.raises(
        AutonomousControlledAuthorizationBridgeError,
        match="record hash is invalid",
    ):
        create_autonomous_authorization_intent(
            request_record=tampered,
            request_audit=audit,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "authorization_created",
            True,
        ),
        (
            "authorization_approved",
            True,
        ),
        (
            "authorization_token_created",
            True,
        ),
        (
            "execution_lease_created",
            True,
        ),
        (
            "execution_allowed",
            True,
        ),
        (
            "can_execute",
            True,
        ),
    ],
)
def test_unsafe_request_claim_rejected(
    tmp_path,
    field,
    value,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    payload = dict(
        record.request_payload
    )

    payload[field] = value

    tampered = replace(
        record,
        request_payload=payload,
    )

    with pytest.raises(
        AutonomousControlledAuthorizationBridgeError,
    ):
        create_autonomous_authorization_intent(
            request_record=tampered,
            request_audit=audit,
        )


def test_invalid_argument_types_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="request_record",
    ):
        create_autonomous_authorization_intent(
            request_record="invalid",
            request_audit=audit,
        )

    with pytest.raises(
        TypeError,
        match="request_audit",
    ):
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit="invalid",
        )


def test_tampered_intent_fingerprint_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    intent = (
        create_autonomous_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    with pytest.raises(
        ValueError,
        match="bridge_fingerprint",
    ):
        replace(
            intent,
            bridge_fingerprint="0" * 64,
        )
