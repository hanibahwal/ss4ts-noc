from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.services.autonomous_proposal_audit import (
    AutonomousProposalAuditReport,
    verify_autonomous_proposal_store,
)
from app.services.autonomous_proposal_store import (
    AutonomousProposalRecord,
    AutonomousProposalStore,
)


SERVICE_NAME = (
    "SS4TS Autonomous Proposal Review Queue"
)

SERVICE_VERSION = "1.0.0"


class AutonomousReviewStatus(
    str,
    Enum,
):
    PENDING_REVIEW = "pending_review"


RISK_PRIORITY = {
    "critical": 400,
    "high": 300,
    "medium": 200,
    "low": 100,
}


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _is_expired(
    expires_at: Any,
    *,
    now: datetime,
) -> bool:
    parsed = _parse_datetime(
        expires_at
    )

    if parsed is None:
        return False

    return parsed <= now


def _priority_score(
    *,
    risk_level: str,
    confidence_percent: float,
    created_at: datetime | None,
    now: datetime,
) -> float:
    risk_score = RISK_PRIORITY.get(
        risk_level.strip().lower(),
        0,
    )

    confidence_score = max(
        0.0,
        min(
            float(
                confidence_percent
            ),
            100.0,
        ),
    )

    age_hours = 0.0

    if created_at is not None:
        age_seconds = max(
            0.0,
            (
                now
                - created_at
            ).total_seconds(),
        )

        age_hours = min(
            age_seconds / 3600.0,
            168.0,
        )

    return round(
        risk_score
        + confidence_score
        + age_hours,
        6,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousProposalReviewQueueItem:
    queue_item_id: str
    sequence_number: int

    proposal_id: str
    decision_id: str | None
    plan_id: str | None

    target_node_id: str
    operation_type: str
    summary: str
    reason: str

    risk_level: str
    confidence_percent: float

    created_at: str
    expires_at: str | None

    priority_score: float
    review_status: AutonomousReviewStatus
    review_required: bool

    record_hash: str

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "queue_item_id":
                self.queue_item_id,
            "sequence_number":
                self.sequence_number,
            "proposal_id":
                self.proposal_id,
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
            "risk_level":
                self.risk_level,
            "confidence_percent":
                self.confidence_percent,
            "created_at":
                self.created_at,
            "expires_at":
                self.expires_at,
            "priority_score":
                self.priority_score,
            "review_status":
                self.review_status.value,
            "review_required":
                self.review_required,
            "record_hash":
                self.record_hash,
            "can_execute":
                False,
            "safety": {
                "read_only_projection":
                    True,
                "immutable_ledger_modified":
                    False,
                "approval_decision_created":
                    False,
                "authorization_created":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "automatic_execution_allowed":
                    False,
            },
        }


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousProposalReviewQueueResult:
    generated_at: str
    audit_id: str
    audit_valid: bool

    source_record_count: int
    eligible_record_count: int
    excluded_record_count: int

    items: tuple[
        AutonomousProposalReviewQueueItem,
        ...
    ]

    warnings: tuple[str, ...]

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "generated_at":
                self.generated_at,
            "audit_id":
                self.audit_id,
            "audit_valid":
                self.audit_valid,
            "source_record_count":
                self.source_record_count,
            "eligible_record_count":
                self.eligible_record_count,
            "excluded_record_count":
                self.excluded_record_count,
            "items": [
                item.to_dict()
                for item in self.items
            ],
            "warnings":
                list(
                    self.warnings
                ),
            "can_execute":
                False,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "read_only_projection":
                    True,
                "database_write_performed":
                    False,
                "approval_decision_created":
                    False,
                "authorization_created":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "automatic_execution_allowed":
                    False,
            },
        }


class AutonomousProposalReviewQueue:
    """
    Build a read-only human review projection from the
    immutable autonomous proposal ledger.

    The queue does not claim, approve, reject, authorize,
    simulate, or execute proposals.
    """

    def __init__(
        self,
        store: AutonomousProposalStore,
    ) -> None:
        if not isinstance(
            store,
            AutonomousProposalStore,
        ):
            raise TypeError(
                "store must be an "
                "AutonomousProposalStore"
            )

        self.store = store

    @staticmethod
    def _eligible(
        record: AutonomousProposalRecord,
        *,
        now: datetime,
    ) -> bool:
        proposal = record.proposal_payload
        policy = record.policy_payload
        binding = record.binding_payload

        checks = binding.get(
            "checks",
            {},
        )

        if not isinstance(
            checks,
            dict,
        ):
            return False

        if not bool(
            policy.get(
                "allowed_for_review",
                False,
            )
        ):
            return False

        if bool(
            policy.get(
                "blocked",
                True,
            )
        ):
            return False

        if not bool(
            binding.get(
                "binding_valid",
                False,
            )
        ):
            return False

        if not bool(
            checks.get(
                "policy_review_allowed",
                False,
            )
        ):
            return False

        if not bool(
            checks.get(
                "proposal_not_expired",
                False,
            )
        ):
            return False

        if not bool(
            checks.get(
                "human_approval_required",
                False,
            )
        ):
            return False

        if not bool(
            checks.get(
                "dry_run_only",
                False,
            )
        ):
            return False

        if not bool(
            proposal.get(
                "requires_human_approval",
                False,
            )
        ):
            return False

        if _is_expired(
            proposal.get(
                "expires_at"
            ),
            now=now,
        ):
            return False

        return True

    @staticmethod
    def _queue_item(
        record: AutonomousProposalRecord,
        *,
        now: datetime,
    ) -> AutonomousProposalReviewQueueItem:
        proposal = record.proposal_payload
        binding = record.binding_payload

        risk_level = str(
            proposal.get(
                "risk_level",
                "low",
            )
        ).strip().lower()

        confidence_percent = float(
            proposal.get(
                "confidence_percent",
                0.0,
            )
        )

        created_at_text = str(
            proposal.get(
                "created_at",
                record.created_at,
            )
        )

        expires_at_value = proposal.get(
            "expires_at"
        )

        expires_at_text = (
            str(
                expires_at_value
            )
            if expires_at_value
            is not None
            else None
        )

        created_at = _parse_datetime(
            created_at_text
        )

        return AutonomousProposalReviewQueueItem(
            queue_item_id=(
                f"review:{record.proposal_id}"
            ),
            sequence_number=(
                record.sequence_number
            ),
            proposal_id=(
                record.proposal_id
            ),
            decision_id=(
                binding.get(
                    "decision_id"
                )
                or proposal.get(
                    "decision_id"
                )
            ),
            plan_id=(
                binding.get(
                    "plan_id"
                )
                or proposal.get(
                    "plan_id"
                )
            ),
            target_node_id=str(
                proposal.get(
                    "target_node_id",
                    "",
                )
            ),
            operation_type=str(
                proposal.get(
                    "operation_type",
                    "",
                )
            ),
            summary=str(
                proposal.get(
                    "summary",
                    "",
                )
            ),
            reason=str(
                proposal.get(
                    "reason",
                    "",
                )
            ),
            risk_level=risk_level,
            confidence_percent=(
                confidence_percent
            ),
            created_at=created_at_text,
            expires_at=expires_at_text,
            priority_score=(
                _priority_score(
                    risk_level=risk_level,
                    confidence_percent=(
                        confidence_percent
                    ),
                    created_at=created_at,
                    now=now,
                )
            ),
            review_status=(
                AutonomousReviewStatus
                .PENDING_REVIEW
            ),
            review_required=True,
            record_hash=(
                record.record_hash
            ),
        )

    def build(
        self,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> AutonomousProposalReviewQueueResult:
        safe_limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        resolved_now = (
            now
            or datetime.now(
                timezone.utc
            )
        )

        if (
            resolved_now.tzinfo
            is None
        ):
            resolved_now = (
                resolved_now.replace(
                    tzinfo=timezone.utc
                )
            )

        resolved_now = (
            resolved_now.astimezone(
                timezone.utc
            )
        )

        audit: AutonomousProposalAuditReport = (
            verify_autonomous_proposal_store(
                self.store
            )
        )

        if not audit.audit_valid:
            return AutonomousProposalReviewQueueResult(
                generated_at=(
                    resolved_now.isoformat()
                ),
                audit_id=audit.audit_id,
                audit_valid=False,
                source_record_count=(
                    audit.record_count
                ),
                eligible_record_count=0,
                excluded_record_count=(
                    audit.record_count
                ),
                items=(),
                warnings=(
                    "Review queue suppressed because "
                    "the immutable ledger audit failed",
                ),
            )

        records = self.store.list_records(
            limit=1000
        )

        items = [
            self._queue_item(
                record,
                now=resolved_now,
            )
            for record in records
            if self._eligible(
                record,
                now=resolved_now,
            )
        ]

        items.sort(
            key=lambda item: (
                -item.priority_score,
                item.created_at,
                item.sequence_number,
                item.proposal_id,
            )
        )

        selected = tuple(
            items[
                :safe_limit
            ]
        )

        warnings: list[str] = []

        if not selected:
            warnings.append(
                "No autonomous proposals are "
                "eligible for human review"
            )

        return AutonomousProposalReviewQueueResult(
            generated_at=(
                resolved_now.isoformat()
            ),
            audit_id=audit.audit_id,
            audit_valid=True,
            source_record_count=len(
                records
            ),
            eligible_record_count=len(
                items
            ),
            excluded_record_count=(
                len(
                    records
                )
                - len(
                    items
                )
            ),
            items=selected,
            warnings=tuple(
                warnings
            ),
        )


def build_autonomous_proposal_review_queue(
    store: AutonomousProposalStore,
    *,
    limit: int = 100,
    now: datetime | None = None,
) -> AutonomousProposalReviewQueueResult:
    return AutonomousProposalReviewQueue(
        store
    ).build(
        limit=limit,
        now=now,
    )
