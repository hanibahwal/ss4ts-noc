from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def _canonical_json(
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


@dataclass(frozen=True, slots=True)
class ControlledExecutionReceipt:
    execution_id: str
    approval_id: str
    intent_fingerprint: str
    intent_version: str

    router_ip: str
    action_type: str
    mode: str
    status: str

    approval_status_before: str
    approval_status_after: str | None

    verification_status: str | None
    failure_reason: str | None

    started_at: str
    completed_at: str | None

    network_io_attempted: bool = False
    network_io_performed: bool = False
    device_command_executed: bool = False

    def __post_init__(self) -> None:
        required = (
            "execution_id",
            "approval_id",
            "intent_fingerprint",
            "intent_version",
            "router_ip",
            "action_type",
            "mode",
            "status",
            "approval_status_before",
            "started_at",
        )

        for field_name in required:
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

        if self.device_command_executed:
            raise ValueError(
                "Controlled execution receipt "
                "cannot claim device command execution"
            )

        if (
            (
                self.network_io_attempted
                or self.network_io_performed
            )
            and self.mode != "CANARY_READ_ONLY"
        ):
            raise ValueError(
                "Network I/O is allowed only for "
                "CANARY_READ_ONLY receipts"
            )

        datetime.fromisoformat(
            self.started_at
        )

        if self.completed_at is not None:
            datetime.fromisoformat(
                self.completed_at
            )

    @property
    def checksum_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "execution_id":
                self.execution_id,
            "approval_id":
                self.approval_id,
            "intent_fingerprint":
                self.intent_fingerprint,
            "intent_version":
                self.intent_version,
            "router_ip":
                self.router_ip,
            "action_type":
                self.action_type,
            "mode":
                self.mode,
            "status":
                self.status,
            "approval_status_before":
                self.approval_status_before,
            "approval_status_after":
                self.approval_status_after,
            "verification_status":
                self.verification_status,
            "failure_reason":
                self.failure_reason,
            "started_at":
                self.started_at,
            "completed_at":
                self.completed_at,
            "network_io_attempted":
                self.network_io_attempted,
            "network_io_performed":
                self.network_io_performed,
            "device_command_executed":
                self.device_command_executed,
        }

    @property
    def checksum(self) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.checksum_payload
            ).encode("utf-8")
        ).hexdigest()

    def verify(
        self,
        checksum: str,
    ) -> bool:
        return (
            self.checksum
            == str(checksum).strip()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.checksum_payload,
            "checksum":
                self.checksum,
            "checksum_algorithm":
                "sha256",
            "integrity":
                "valid",
            "safety": {
                "network_io_attempted":
                    self.network_io_attempted,
                "network_io_performed":
                    self.network_io_performed,
                "device_command_executed":
                    self.device_command_executed,
                "read_only":
                    not self.device_command_executed,
                "secrets_exposed":
                    False,
                "command_payload_exposed":
                    False,
            },
        }


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()
