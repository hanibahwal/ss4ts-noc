from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Any


class DecisionAuditStatus(StrEnum):
    RECORDED = "recorded"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _optional_text(
    value: Any,
) -> str | None:
    text = _text(value)

    return text or None


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(number):
        return default

    return number


def _datetime(
    value: Any,
) -> datetime:
    if isinstance(value, datetime):
        return value

    text = _text(value)

    if text:
        try:
            return datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            pass

    return datetime.now(
        timezone.utc
    )


def _status(
    value: Any,
) -> DecisionAuditStatus:
    normalized = _text(
        value,
        DecisionAuditStatus.UNKNOWN,
    ).lower().replace("-", "_")

    try:
        return DecisionAuditStatus(
            normalized
        )
    except ValueError:
        return DecisionAuditStatus.UNKNOWN


def _payload(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        return {}

    return dict(value)


@dataclass(slots=True)
class DecisionAuditRecord:
    audit_id: str
    trace_id: str
    decision_id: str
    source_node_id: str

    created_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    status: DecisionAuditStatus = (
        DecisionAuditStatus.RECORDED
    )

    risk_level: str = "unknown"
    risk_score: float = 0.0

    primary_cause_id: str | None = None

    trace_payload: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    explanation_payload: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    execution_plan_payload: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    simulation_payload: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    checksum: str = ""

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.audit_id = _text(
            self.audit_id
        )

        self.trace_id = _text(
            self.trace_id
        )

        self.decision_id = _text(
            self.decision_id
        )

        self.source_node_id = _text(
            self.source_node_id
        )

        self.created_at = _datetime(
            self.created_at
        )

        self.status = _status(
            self.status
        )

        self.risk_level = _text(
            self.risk_level,
            "unknown",
        ).lower()

        self.risk_score = round(
            max(
                _number(
                    self.risk_score
                ),
                0.0,
            ),
            2,
        )

        self.primary_cause_id = (
            _optional_text(
                self.primary_cause_id
            )
        )

        self.trace_payload = _payload(
            self.trace_payload
        )

        self.explanation_payload = _payload(
            self.explanation_payload
        )

        self.execution_plan_payload = _payload(
            self.execution_plan_payload
        )

        self.simulation_payload = _payload(
            self.simulation_payload
        )

        self.checksum = _text(
            self.checksum
        ).lower()

        self.metadata = _payload(
            self.metadata
        )

        if not self.audit_id:
            raise ValueError(
                "Decision audit_id must not be empty"
            )

        if not self.trace_id:
            raise ValueError(
                "Decision audit trace_id must not be empty"
            )

        if not self.decision_id:
            raise ValueError(
                "Decision audit decision_id must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "Decision audit source_node_id must not be empty"
            )

        if self.checksum and (
            len(self.checksum) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in self.checksum
            )
        ):
            raise ValueError(
                "Decision audit checksum must be SHA-256 hexadecimal"
            )

    @property
    def has_explanation(
        self,
    ) -> bool:
        return bool(
            self.explanation_payload
        )

    @property
    def has_execution_plan(
        self,
    ) -> bool:
        return bool(
            self.execution_plan_payload
        )

    @property
    def has_simulation(
        self,
    ) -> bool:
        return bool(
            self.simulation_payload
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionAuditRecord:
        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Decision audit data must be a dictionary"
            )

        return cls(
            audit_id=_text(
                data.get("audit_id")
                or data.get("id")
            ),
            trace_id=_text(
                data.get("trace_id")
            ),
            decision_id=_text(
                data.get("decision_id")
            ),
            source_node_id=_text(
                data.get("source_node_id")
                or data.get("source")
            ),
            created_at=_datetime(
                data.get("created_at")
            ),
            status=_status(
                data.get("status")
            ),
            risk_level=_text(
                data.get(
                    "risk_level",
                    "unknown",
                )
            ),
            risk_score=_number(
                data.get(
                    "risk_score",
                    0.0,
                )
            ),
            primary_cause_id=(
                _optional_text(
                    data.get(
                        "primary_cause_id"
                    )
                )
            ),
            trace_payload=_payload(
                data.get(
                    "trace_payload"
                    or {}
                )
            ),
            explanation_payload=_payload(
                data.get(
                    "explanation_payload"
                    or {}
                )
            ),
            execution_plan_payload=_payload(
                data.get(
                    "execution_plan_payload"
                    or {}
                )
            ),
            simulation_payload=_payload(
                data.get(
                    "simulation_payload"
                    or {}
                )
            ),
            checksum=_text(
                data.get("checksum")
            ),
            metadata=_payload(
                data.get(
                    "metadata"
                    or {}
                )
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "id":
                self.audit_id,
            "trace_id":
                self.trace_id,
            "decision_id":
                self.decision_id,
            "source_node_id":
                self.source_node_id,
            "created_at":
                self.created_at.isoformat(),
            "status":
                self.status.value,
            "risk_level":
                self.risk_level,
            "risk_score":
                self.risk_score,
            "primary_cause_id":
                self.primary_cause_id,
            "trace_payload":
                dict(self.trace_payload),
            "explanation_payload":
                dict(
                    self.explanation_payload
                ),
            "execution_plan_payload":
                dict(
                    self.execution_plan_payload
                ),
            "simulation_payload":
                dict(
                    self.simulation_payload
                ),
            "checksum":
                self.checksum,
            "content": {
                "has_explanation":
                    self.has_explanation,
                "has_execution_plan":
                    self.has_execution_plan,
                "has_simulation":
                    self.has_simulation,
            },
            "metadata":
                dict(self.metadata),
        }


def normalize_decision_audit(
    value: Any,
) -> DecisionAuditRecord | None:
    if isinstance(
        value,
        DecisionAuditRecord,
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return DecisionAuditRecord.from_dict(
            value
        )

    return None
