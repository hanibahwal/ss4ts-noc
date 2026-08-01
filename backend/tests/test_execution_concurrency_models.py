from __future__ import annotations

import pytest

from app.models.execution_concurrency import (
    AuthorizationMutationAction,
    AuthorizationMutationResult,
    AuthorizationMutationToken,
    AuthorizationVersionConflict,
    IdempotencyConflict,
    IdempotencyDisposition,
    calculate_request_fingerprint,
    canonical_mutation_json,
)


def make_token(
    **overrides,
) -> AuthorizationMutationToken:
    values = {
        "authorization_id":
            "authorization:1",
        "action":
            AuthorizationMutationAction
            .APPROVE,
        "expected_version":
            1,
        "idempotency_key":
            "approve-request-001",
        "actor_identity_id":
            "user:senior",
        "payload": {
            "role":
                "senior_engineer",
        },
    }

    values.update(
        overrides
    )

    return AuthorizationMutationToken(
        **values
    )


def test_canonical_json_is_deterministic() -> None:
    first = canonical_mutation_json({
        "b": 2,
        "a": 1,
    })

    second = canonical_mutation_json({
        "a": 1,
        "b": 2,
    })

    assert first == second


def test_fingerprint_is_deterministic() -> None:
    first = calculate_request_fingerprint(
        authorization_id=
            "authorization:1",
        action=(
            AuthorizationMutationAction
            .APPROVE
        ),
        expected_version=1,
        actor_identity_id=
            "user:senior",
        payload={
            "b": 2,
            "a": 1,
        },
    )

    second = calculate_request_fingerprint(
        authorization_id=
            "authorization:1",
        action=(
            AuthorizationMutationAction
            .APPROVE
        ),
        expected_version=1,
        actor_identity_id=
            "user:senior",
        payload={
            "a": 1,
            "b": 2,
        },
    )

    assert first == second
    assert len(first) == 64


def test_token_generates_fingerprint() -> None:
    token = make_token()

    assert len(
        token.request_fingerprint
    ) == 64

    assert (
        token.action
        == AuthorizationMutationAction
        .APPROVE
    )


def test_token_serializes() -> None:
    payload = make_token().to_dict()

    assert (
        payload["expected_version"]
        == 1
    )

    assert (
        payload["idempotency_key"]
        == "approve-request-001"
    )


def test_token_rejects_bad_version() -> None:
    with pytest.raises(
        ValueError,
        match="expected_version",
    ):
        make_token(
            expected_version=0
        )


def test_token_rejects_empty_key() -> None:
    with pytest.raises(
        ValueError,
        match="idempotency_key",
    ):
        make_token(
            idempotency_key=""
        )


def test_token_rejects_changed_fingerprint() -> None:
    with pytest.raises(
        ValueError,
        match="fingerprint",
    ):
        make_token(
            request_fingerprint=(
                "0" * 64
            )
        )


def test_version_conflict_details() -> None:
    conflict = AuthorizationVersionConflict(
        authorization_id=
            "authorization:1",
        expected_version=1,
        actual_version=2,
    )

    assert conflict.expected_version == 1
    assert conflict.actual_version == 2

    assert "expected=1" in str(conflict)
    assert "actual=2" in str(conflict)


def test_idempotency_conflict_details() -> None:
    conflict = IdempotencyConflict(
        idempotency_key=
            "approve-request-001"
    )

    assert (
        conflict.idempotency_key
        == "approve-request-001"
    )

    assert "different request" in str(
        conflict
    )


def test_mutation_result_new_request() -> None:
    token = make_token()

    result = AuthorizationMutationResult(
        authorization_id=
            token.authorization_id,
        action=token.action,
        previous_version=1,
        current_version=2,
        disposition=(
            IdempotencyDisposition.NEW
        ),
        idempotency_key=
            token.idempotency_key,
        request_fingerprint=
            token.request_fingerprint,
        response_payload={
            "status":
                "approved",
        },
    )

    assert result.replayed is False
    assert result.version_advanced is True


def test_mutation_result_replay() -> None:
    token = make_token()

    result = AuthorizationMutationResult(
        authorization_id=
            token.authorization_id,
        action=token.action,
        previous_version=1,
        current_version=2,
        disposition=(
            IdempotencyDisposition.REPLAY
        ),
        idempotency_key=
            token.idempotency_key,
        request_fingerprint=
            token.request_fingerprint,
    )

    assert result.replayed is True


def test_result_rejects_invalid_hash() -> None:
    with pytest.raises(
        ValueError,
        match="SHA-256",
    ):
        AuthorizationMutationResult(
            authorization_id=
                "authorization:1",
            action=(
                AuthorizationMutationAction
                .APPROVE
            ),
            previous_version=1,
            current_version=2,
            disposition=(
                IdempotencyDisposition.NEW
            ),
            idempotency_key="key-1",
            request_fingerprint="bad",
        )
