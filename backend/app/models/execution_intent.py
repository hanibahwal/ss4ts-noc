from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


INTENT_VERSION = "1.0"


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _parse_datetime(
    value: str | datetime,
) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(
            str(value)
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    approval_id: str
    router_ip: str
    action_type: str

    execution_class: str
    read_only: bool
    verification_required: bool
    rollback_required: bool

    expires_at: str
    intent_version: str = INTENT_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "approval_id",
            "router_ip",
            "action_type",
            "execution_class",
            "expires_at",
            "intent_version",
        ):
            value = str(
                getattr(
                    self,
                    field_name,
                )
            ).strip()

            if not value:
                raise ValueError(
                    f"{field_name} is required"
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        _parse_datetime(
            self.expires_at
        )

    @property
    def canonical_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "action_type":
                self.action_type,
            "approval_id":
                self.approval_id,
            "execution_class":
                self.execution_class,
            "expires_at":
                _parse_datetime(
                    self.expires_at
                ).isoformat(),
            "intent_version":
                self.intent_version,
            "read_only":
                self.read_only,
            "rollback_required":
                self.rollback_required,
            "router_ip":
                self.router_ip,
            "verification_required":
                self.verification_required,
        }

    @property
    def fingerprint(self) -> str:
        serialized = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    @property
    def expired(self) -> bool:
        return (
            _parse_datetime(
                self.expires_at
            )
            <= _utc_now()
        )

    def verify_fingerprint(
        self,
        fingerprint: str,
    ) -> bool:
        return (
            self.fingerprint
            == str(
                fingerprint
            ).strip()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.canonical_payload,
            "intent_fingerprint":
                self.fingerprint,
            "expired":
                self.expired,
        }
