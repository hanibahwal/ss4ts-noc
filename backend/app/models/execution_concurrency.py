from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AuthorizationMutationAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REVOKE = "revoke"
    CONSUME = "consume"
    EXPIRE = "expire"
    UNKNOWN = "unknown"


class IdempotencyDisposition(StrEnum):
    NEW = "new"
    REPLAY = "replay"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


class AuthorizationConcurrencyError(
    RuntimeError
):
    """
    Base class for authorization concurrency failures.
    """


class AuthorizationVersionConflict(
    AuthorizationConcurrencyError
):
    def __init__(
        self,
        *,
        authorization_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.authorization_id = str(
            authorization_id
        ).strip()

        self.expected_version = int(
            expected_version
        )

        self.actual_version = int(
            actual_version
        )

        super().__init__(
            "Authorization version conflict: "
            f"expected={self.expected_version}, "
            f"actual={self.actual_version}"
        )


class IdempotencyConflict(
    AuthorizationConcurrencyError
):
    def __init__(
        self,
        *,
        idempotency_key: str,
    ) -> None:
        self.idempotency_key = str(
            idempotency_key
        ).strip()

        super().__init__(
            "Idempotency key was already used "
            "with a different request"
        )


def _text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def canonical_mutation_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def calculate_request_fingerprint(
    *,
    authorization_id: str,
    action: AuthorizationMutationAction,
    expected_version: int,
    actor_identity_id: str,
    payload: dict[str, Any] | None = None,
) -> str:
    content = {
        "authorization_id":
            _text(authorization_id),
        "action":
            action.value,
        "expected_version":
            int(expected_version),
        "actor_identity_id":
            _text(actor_identity_id),
        "payload":
            dict(payload or {}),
    }

    return hashlib.sha256(
        canonical_mutation_json(
            content
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    slots=True,
    frozen=True,
)
class AuthorizationMutationToken:
    authorization_id: str

    action: AuthorizationMutationAction

    expected_version: int

    idempotency_key: str

    actor_identity_id: str

    request_fingerprint: str = ""

    payload: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        authorization_id = _text(
            self.authorization_id
        )

        idempotency_key = _text(
            self.idempotency_key
        )

        actor_identity_id = _text(
            self.actor_identity_id
        )

        try:
            action = (
                self.action
                if isinstance(
                    self.action,
                    AuthorizationMutationAction,
                )
                else AuthorizationMutationAction(
                    _text(
                        self.action
                    ).lower()
                )
            )
        except ValueError:
            action = (
                AuthorizationMutationAction
                .UNKNOWN
            )

        expected_version = int(
            self.expected_version
        )

        payload = (
            dict(self.payload)
            if isinstance(
                self.payload,
                dict,
            )
            else {}
        )

        if not authorization_id:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if (
            action
            == AuthorizationMutationAction.UNKNOWN
        ):
            raise ValueError(
                "Mutation action must be known"
            )

        if expected_version < 1:
            raise ValueError(
                "expected_version must be at least 1"
            )

        if not idempotency_key:
            raise ValueError(
                "idempotency_key must not be empty"
            )

        if len(idempotency_key) > 200:
            raise ValueError(
                "idempotency_key is too long"
            )

        if not actor_identity_id:
            raise ValueError(
                "actor_identity_id must not be empty"
            )

        calculated = (
            calculate_request_fingerprint(
                authorization_id=
                    authorization_id,
                action=action,
                expected_version=
                    expected_version,
                actor_identity_id=
                    actor_identity_id,
                payload=payload,
            )
        )

        supplied_fingerprint = _text(
            self.request_fingerprint
        ).lower()

        if (
            supplied_fingerprint
            and supplied_fingerprint
            != calculated
        ):
            raise ValueError(
                "request_fingerprint does not "
                "match mutation content"
            )

        object.__setattr__(
            self,
            "authorization_id",
            authorization_id,
        )

        object.__setattr__(
            self,
            "action",
            action,
        )

        object.__setattr__(
            self,
            "expected_version",
            expected_version,
        )

        object.__setattr__(
            self,
            "idempotency_key",
            idempotency_key,
        )

        object.__setattr__(
            self,
            "actor_identity_id",
            actor_identity_id,
        )

        object.__setattr__(
            self,
            "payload",
            payload,
        )

        object.__setattr__(
            self,
            "request_fingerprint",
            calculated,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "authorization_id":
                self.authorization_id,
            "action":
                self.action.value,
            "expected_version":
                self.expected_version,
            "idempotency_key":
                self.idempotency_key,
            "actor_identity_id":
                self.actor_identity_id,
            "request_fingerprint":
                self.request_fingerprint,
            "payload":
                dict(self.payload),
        }


@dataclass(
    slots=True,
    frozen=True,
)
class AuthorizationMutationResult:
    authorization_id: str

    action: AuthorizationMutationAction

    previous_version: int

    current_version: int

    disposition: IdempotencyDisposition

    idempotency_key: str

    request_fingerprint: str

    response_payload: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        authorization_id = _text(
            self.authorization_id
        )

        idempotency_key = _text(
            self.idempotency_key
        )

        request_fingerprint = _text(
            self.request_fingerprint
        ).lower()

        previous_version = int(
            self.previous_version
        )

        current_version = int(
            self.current_version
        )

        if not authorization_id:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if previous_version < 1:
            raise ValueError(
                "previous_version must be at least 1"
            )

        if current_version < previous_version:
            raise ValueError(
                "current_version cannot be older "
                "than previous_version"
            )

        if not idempotency_key:
            raise ValueError(
                "idempotency_key must not be empty"
            )

        if len(request_fingerprint) != 64:
            raise ValueError(
                "request_fingerprint must be SHA-256"
            )

        if any(
            character
            not in "0123456789abcdef"
            for character in request_fingerprint
        ):
            raise ValueError(
                "request_fingerprint must be hexadecimal"
            )

        object.__setattr__(
            self,
            "authorization_id",
            authorization_id,
        )

        object.__setattr__(
            self,
            "previous_version",
            previous_version,
        )

        object.__setattr__(
            self,
            "current_version",
            current_version,
        )

        object.__setattr__(
            self,
            "idempotency_key",
            idempotency_key,
        )

        object.__setattr__(
            self,
            "request_fingerprint",
            request_fingerprint,
        )

        object.__setattr__(
            self,
            "response_payload",
            dict(
                self.response_payload
            ),
        )

    @property
    def replayed(
        self,
    ) -> bool:
        return (
            self.disposition
            == IdempotencyDisposition.REPLAY
        )

    @property
    def version_advanced(
        self,
    ) -> bool:
        return (
            self.current_version
            > self.previous_version
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "authorization_id":
                self.authorization_id,
            "action":
                self.action.value,
            "previous_version":
                self.previous_version,
            "current_version":
                self.current_version,
            "disposition":
                self.disposition.value,
            "idempotency_key":
                self.idempotency_key,
            "request_fingerprint":
                self.request_fingerprint,
            "replayed":
                self.replayed,
            "version_advanced":
                self.version_advanced,
            "response_payload":
                dict(
                    self.response_payload
                ),
        }
