from __future__ import annotations

import hashlib
import json
import uuid

from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from enum import StrEnum
from typing import Any


PROPOSAL_VERSION = "1.0"


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _text(
    value: Any,
    *,
    field_name: str,
) -> str:
    normalized = str(
        value
        if value is not None
        else ""
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _optional_text(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    return normalized or None


def _confidence(
    value: Any,
) -> float:
    try:
        confidence = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "confidence_percent must be numeric"
        ) from exc

    if not 0 <= confidence <= 100:
        raise ValueError(
            "confidence_percent must be "
            "between 0 and 100"
        )

    return round(
        confidence,
        2,
    )


def _datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if value.tzinfo is None:
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


def _unique_texts(
    values: Any,
) -> tuple[str, ...]:
    if values is None:
        return ()

    if isinstance(
        values,
        str,
    ):
        values = (
            values,
        )

    normalized: list[str] = []
    seen: set[str] = set()

    for item in values:
        text = str(
            item
        ).strip()

        if not text:
            continue

        if text in seen:
            continue

        normalized.append(
            text
        )

        seen.add(
            text
        )

    return tuple(
        normalized
    )


class AutonomousOperationMode(
    StrEnum
):
    ADVISORY_ONLY = (
        "advisory_only"
    )

    APPROVAL_CANDIDATE = (
        "approval_candidate"
    )


class AutonomousPolicyStatus(
    StrEnum
):
    PENDING_EVALUATION = (
        "pending_evaluation"
    )

    ALLOWED_FOR_REVIEW = (
        "allowed_for_review"
    )

    BLOCKED = "blocked"


class AutonomousProposalRiskLevel(
    StrEnum
):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class AutonomousOperationProposal:
    source_signal_id: str
    target_node_id: str
    operation_type: str
    summary: str
    reason: str
    confidence_percent: float
    risk_level: AutonomousProposalRiskLevel

    proposal_id: str = field(
        default_factory=lambda: (
            f"autonomous-proposal:{uuid.uuid4()}"
        )
    )

    proposal_version: str = (
        PROPOSAL_VERSION
    )

    decision_id: str | None = None
    plan_id: str | None = None

    policy_status: AutonomousPolicyStatus = (
        AutonomousPolicyStatus
        .PENDING_EVALUATION
    )

    operating_mode: AutonomousOperationMode = (
        AutonomousOperationMode
        .ADVISORY_ONLY
    )

    requires_human_approval: bool = (
        True
    )

    idempotency_key: str | None = None

    evidence_references: tuple[
        str,
        ...,
    ] = ()

    policy_reasons: tuple[
        str,
        ...,
    ] = ()

    created_at: datetime = field(
        default_factory=utc_now
    )

    expires_at: datetime | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.proposal_id = _text(
            self.proposal_id,
            field_name="proposal_id",
        )

        self.proposal_version = _text(
            self.proposal_version,
            field_name="proposal_version",
        )

        self.source_signal_id = _text(
            self.source_signal_id,
            field_name="source_signal_id",
        )

        self.target_node_id = _text(
            self.target_node_id,
            field_name="target_node_id",
        )

        self.operation_type = _text(
            self.operation_type,
            field_name="operation_type",
        )

        self.summary = _text(
            self.summary,
            field_name="summary",
        )

        self.reason = _text(
            self.reason,
            field_name="reason",
        )

        self.decision_id = _optional_text(
            self.decision_id
        )

        self.plan_id = _optional_text(
            self.plan_id
        )

        self.idempotency_key = (
            _optional_text(
                self.idempotency_key
            )
        )

        self.confidence_percent = (
            _confidence(
                self.confidence_percent
            )
        )

        if not isinstance(
            self.risk_level,
            AutonomousProposalRiskLevel,
        ):
            self.risk_level = (
                AutonomousProposalRiskLevel(
                    str(
                        self.risk_level
                    ).strip().lower()
                )
            )

        if not isinstance(
            self.policy_status,
            AutonomousPolicyStatus,
        ):
            self.policy_status = (
                AutonomousPolicyStatus(
                    str(
                        self.policy_status
                    ).strip().lower()
                )
            )

        if not isinstance(
            self.operating_mode,
            AutonomousOperationMode,
        ):
            self.operating_mode = (
                AutonomousOperationMode(
                    str(
                        self.operating_mode
                    ).strip().lower()
                )
            )

        self.created_at = _datetime(
            self.created_at,
            field_name="created_at",
        )

        if self.expires_at is not None:
            self.expires_at = _datetime(
                self.expires_at,
                field_name="expires_at",
            )

            if (
                self.expires_at
                <= self.created_at
            ):
                raise ValueError(
                    "expires_at must be after created_at"
                )

        self.evidence_references = (
            _unique_texts(
                self.evidence_references
            )
        )

        self.policy_reasons = (
            _unique_texts(
                self.policy_reasons
            )
        )

        self.metadata = dict(
            self.metadata
            or {}
        )

        forbidden_operations = {
            "auto_execute",
            "execute_now",
            "bypass_approval",
            "device_command",
            "routeros_command",
        }

        if (
            self.operation_type
            .strip()
            .lower()
            in forbidden_operations
        ):
            raise ValueError(
                "operation_type is forbidden "
                "for autonomous proposals"
            )

        if (
            self.operating_mode
            is AutonomousOperationMode
            .APPROVAL_CANDIDATE
            and not self.requires_human_approval
        ):
            raise ValueError(
                "approval candidates require "
                "human approval"
            )

        if (
            self.policy_status
            is AutonomousPolicyStatus.BLOCKED
            and self.operating_mode
            is not AutonomousOperationMode
            .ADVISORY_ONLY
        ):
            raise ValueError(
                "blocked proposals must remain "
                "advisory-only"
            )

        if (
            self.risk_level
            in {
                AutonomousProposalRiskLevel.HIGH,
                AutonomousProposalRiskLevel.CRITICAL,
            }
            and not self.requires_human_approval
        ):
            raise ValueError(
                "high-risk proposals require "
                "human approval"
            )

    @property
    def is_expired(
        self,
    ) -> bool:
        if self.expires_at is None:
            return False

        return (
            utc_now()
            >= self.expires_at
        )

    @property
    def review_allowed(
        self,
    ) -> bool:
        return (
            not self.is_expired
            and self.policy_status
            is AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
        )

    @property
    def can_execute(
        self,
    ) -> bool:
        """
        Autonomous proposals are never execution authority.

        Execution must continue through the existing H23
        plan, authorization, approval and controlled gate.
        """
        return False

    def canonical_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "proposal_id":
                self.proposal_id,
            "proposal_version":
                self.proposal_version,
            "source_signal_id":
                self.source_signal_id,
            "decision_id":
                self.decision_id,
            "plan_id":
                self.plan_id,
            "target_node_id":
                self.target_node_id,
            "operation_type":
                self.operation_type,
            "summary":
                self.summary,
            "reason":
                self.reason,
            "confidence_percent":
                self.confidence_percent,
            "risk_level":
                self.risk_level.value,
            "policy_status":
                self.policy_status.value,
            "operating_mode":
                self.operating_mode.value,
            "requires_human_approval":
                self.requires_human_approval,
            "idempotency_key":
                self.idempotency_key,
            "evidence_references":
                list(
                    self.evidence_references
                ),
            "policy_reasons":
                list(
                    self.policy_reasons
                ),
            "created_at":
                self.created_at.isoformat(),
            "expires_at": (
                self.expires_at.isoformat()
                if self.expires_at
                else None
            ),
            "metadata":
                dict(
                    self.metadata
                ),
        }

    @property
    def fingerprint(
        self,
    ) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        ).encode(
            "utf-8"
        )

        return hashlib.sha256(
            encoded
        ).hexdigest()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        payload = (
            self.canonical_payload()
        )

        payload.update({
            "fingerprint":
                self.fingerprint,
            "is_expired":
                self.is_expired,
            "review_allowed":
                self.review_allowed,
            "can_execute":
                False,
            "safety": {
                "proposal_only":
                    True,
                "execution_authority":
                    False,
                "human_approval_boundary":
                    True,
                "controlled_execution_required":
                    True,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        })

        return payload


def normalize_autonomous_operation_proposal(
    value: Any,
) -> AutonomousOperationProposal | None:
    if isinstance(
        value,
        AutonomousOperationProposal,
    ):
        return value

    if not isinstance(
        value,
        dict,
    ):
        return None

    try:
        created_at = value.get(
            "created_at",
            utc_now(),
        )

        expires_at = value.get(
            "expires_at"
        )

        if isinstance(
            created_at,
            str,
        ):
            created_at = (
                datetime.fromisoformat(
                    created_at
                )
            )

        if isinstance(
            expires_at,
            str,
        ):
            expires_at = (
                datetime.fromisoformat(
                    expires_at
                )
            )

        return AutonomousOperationProposal(
            proposal_id=value.get(
                "proposal_id",
                (
                    "autonomous-proposal:"
                    f"{uuid.uuid4()}"
                ),
            ),
            proposal_version=value.get(
                "proposal_version",
                PROPOSAL_VERSION,
            ),
            source_signal_id=value.get(
                "source_signal_id"
            ),
            decision_id=value.get(
                "decision_id"
            ),
            plan_id=value.get(
                "plan_id"
            ),
            target_node_id=value.get(
                "target_node_id"
            ),
            operation_type=value.get(
                "operation_type"
            ),
            summary=value.get(
                "summary"
            ),
            reason=value.get(
                "reason"
            ),
            confidence_percent=value.get(
                "confidence_percent",
                value.get(
                    "confidence",
                    0,
                ),
            ),
            risk_level=value.get(
                "risk_level",
                "critical",
            ),
            policy_status=value.get(
                "policy_status",
                "pending_evaluation",
            ),
            operating_mode=value.get(
                "operating_mode",
                "advisory_only",
            ),
            requires_human_approval=bool(
                value.get(
                    "requires_human_approval",
                    True,
                )
            ),
            idempotency_key=value.get(
                "idempotency_key"
            ),
            evidence_references=tuple(
                value.get(
                    "evidence_references",
                    (),
                )
            ),
            policy_reasons=tuple(
                value.get(
                    "policy_reasons",
                    (),
                )
            ),
            created_at=created_at,
            expires_at=expires_at,
            metadata=dict(
                value.get(
                    "metadata",
                    {},
                )
            ),
        )

    except (
        TypeError,
        ValueError,
    ):
        return None
