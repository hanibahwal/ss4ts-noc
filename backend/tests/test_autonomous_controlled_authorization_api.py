from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

from fastapi import HTTPException

from app.api.v1 import (
    autonomous_controlled_authorization,
)
from app.api.v1.router import api_router
from app.services.autonomous_authorization_request_audit import (
    verify_autonomous_authorization_request_store,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestStore,
)
from tests.test_autonomous_authorization_request_store import (
    make_request,
)


NOW = datetime(
    2026,
    8,
    6,
    21,
    0,
    tzinfo=timezone.utc,
)


def run(coroutine):
    return asyncio.run(
        coroutine
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


def test_router_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert any(
        path.endswith(
            "/autonomous-authorizations/"
            "create-intent"
        )
        for path in paths
    )


def test_create_intent_endpoint(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    result = run(
        autonomous_controlled_authorization
        .create_controlled_authorization_intent(
            request_record=record,
            request_audit=audit,
            authorization_intent_id=(
                "autonomous-authorization-intent:"
                "api-test"
            ),
            created_at=NOW,
        )
    )

    assert (
        result["authorization_intent_id"]
        == (
            "autonomous-authorization-intent:"
            "api-test"
        )
    )

    assert (
        result["authorization_request_id"]
        == record.authorization_request_id
    )

    assert (
        result["request_record_hash"]
        == record.record_hash
    )

    assert (
        result["request_audit_id"]
        == audit.audit_id
    )


def test_endpoint_preserves_bindings(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    result = run(
        autonomous_controlled_authorization
        .create_controlled_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        result["authorization_candidate_id"]
        == record.authorization_candidate_id
    )

    assert (
        result["candidate_record_hash"]
        == record.candidate_record_hash
    )

    assert (
        result["candidate_fingerprint"]
        == record.candidate_fingerprint
    )

    assert (
        result["proposal_id"]
        == record.proposal_id
    )

    assert (
        result["proposal_record_hash"]
        == record.proposal_record_hash
    )


def test_endpoint_preserves_policy(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    result = run(
        autonomous_controlled_authorization
        .create_controlled_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        result["requester_id"]
        == record.requester_id
    )

    assert (
        result["request_reason"]
        == record.request_reason
    )

    assert (
        result["risk_class"]
        == record.risk_class
    )

    assert (
        result["dry_run_required"]
        == record.dry_run_required
    )

    assert (
        result["rollback_required"]
        == record.rollback_required
    )

    assert (
        result["verification_required"]
        == record.verification_required
    )


def test_endpoint_never_allows_execution(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    result = run(
        autonomous_controlled_authorization
        .create_controlled_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        result["authorization_intent_created"]
        is True
    )

    assert (
        result["execution_authorization_created"]
        is False
    )

    assert (
        result["authorization_approved"]
        is False
    )

    assert (
        result["authorization_token_created"]
        is False
    )

    assert (
        result["approval_claim_created"]
        is False
    )

    assert (
        result["execution_lease_created"]
        is False
    )

    assert (
        result["execution_allowed"]
        is False
    )

    assert result["can_execute"] is False


def test_endpoint_safety_metadata(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    result = run(
        autonomous_controlled_authorization
        .create_controlled_authorization_intent(
            request_record=record,
            request_audit=audit,
            created_at=NOW,
        )
    )

    assert result["safety"] == {
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


def test_invalid_audit_returns_400(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    invalid_audit = replace(
        audit,
        record_hashes_valid=False,
    )

    try:
        run(
            autonomous_controlled_authorization
            .create_controlled_authorization_intent(
                request_record=record,
                request_audit=invalid_audit,
                created_at=NOW,
            )
        )

    except HTTPException as exc:
        assert exc.status_code == 400
        assert (
            "audit is invalid"
            in str(exc.detail)
        )

    else:
        raise AssertionError(
            "Expected HTTPException"
        )


def test_tampered_record_returns_400(
    tmp_path,
) -> None:
    record, audit = make_verified_inputs(
        tmp_path
    )

    tampered = replace(
        record,
        record_hash="f" * 64,
    )

    try:
        run(
            autonomous_controlled_authorization
            .create_controlled_authorization_intent(
                request_record=tampered,
                request_audit=audit,
                created_at=NOW,
            )
        )

    except HTTPException as exc:
        assert exc.status_code == 400
        assert (
            "record hash is invalid"
            in str(exc.detail)
        )

    else:
        raise AssertionError(
            "Expected HTTPException"
        )


def test_invalid_record_type_returns_400(
    tmp_path,
) -> None:
    _, audit = make_verified_inputs(
        tmp_path
    )

    try:
        run(
            autonomous_controlled_authorization
            .create_controlled_authorization_intent(
                request_record={},
                request_audit=audit,
                created_at=NOW,
            )
        )

    except HTTPException as exc:
        assert exc.status_code == 400
        assert (
            "request_record"
            in str(exc.detail)
        )

    else:
        raise AssertionError(
            "Expected HTTPException"
        )


def test_invalid_audit_type_returns_400(
    tmp_path,
) -> None:
    record, _ = make_verified_inputs(
        tmp_path
    )

    try:
        run(
            autonomous_controlled_authorization
            .create_controlled_authorization_intent(
                request_record=record,
                request_audit={},
                created_at=NOW,
            )
        )

    except HTTPException as exc:
        assert exc.status_code == 400
        assert (
            "request_audit"
            in str(exc.detail)
        )

    else:
        raise AssertionError(
            "Expected HTTPException"
        )
