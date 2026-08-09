from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.decision_audit import (
    DecisionAuditRecord,
)
from app.models.shadow_decision import (
    ShadowDecisionRecord,
)


SERVICE_NAME = (
    "SS4TS Decision Outcome Comparison"
)
SERVICE_VERSION = "1.0.0-H32.3"


@dataclass(frozen=True, slots=True)
class OutcomeComparisonResult:
    shadow_id: str
    decision_id: str
    audit_id: str
    predicted_outcome: dict[str, Any]
    observed_outcome: dict[str, Any]
    field_results: dict[str, bool]
    matched_fields: int
    mismatched_fields: int
    accuracy_percent: float
    overall_match: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "shadow_id":
                self.shadow_id,
            "decision_id":
                self.decision_id,
            "audit_id":
                self.audit_id,
            "predicted_outcome":
                dict(self.predicted_outcome),
            "observed_outcome":
                dict(self.observed_outcome),
            "field_results":
                dict(self.field_results),
            "matched_fields":
                self.matched_fields,
            "mismatched_fields":
                self.mismatched_fields,
            "accuracy_percent":
                self.accuracy_percent,
            "overall_match":
                self.overall_match,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "comparison_only": True,
                "read_only": True,
                "execution_enabled": False,
                "execution_authority": False,
                "network_io_performed": False,
                "device_command_executed": False,
            },
        }


def compare_shadow_to_evidence(
    *,
    shadow: ShadowDecisionRecord,
    audit: DecisionAuditRecord,
) -> OutcomeComparisonResult:
    if not isinstance(
        shadow,
        ShadowDecisionRecord,
    ):
        raise TypeError(
            "shadow must be a ShadowDecisionRecord"
        )

    if not isinstance(
        audit,
        DecisionAuditRecord,
    ):
        raise TypeError(
            "audit must be a DecisionAuditRecord"
        )

    if shadow.decision_id != audit.decision_id:
        raise ValueError(
            "Shadow and audit decision_id "
            "must match"
        )

    predicted = dict(
        shadow.predicted_outcome
    )

    trace = dict(
        audit.trace_payload
    )

    final_outcome = dict(
        trace.get(
            "final_outcome",
            {},
        )
    )

    simulation_payload = dict(
        audit.simulation_payload
    )

    verification = dict(
        simulation_payload.get(
            "verification_summary",
            {},
        )
    )

    execution_plan = dict(
        audit.execution_plan_payload
    )

    observed = {
        "action_status":
            final_outcome.get(
                "action_status"
            ),
        "simulation_status":
            final_outcome.get(
                "simulation_status"
            ),
        "lease_status":
            final_outcome.get(
                "lease_status"
            ),
        "rollback_performed":
            verification.get(
                "rollback_performed"
            ),
        "failed_step_id":
            verification.get(
                "failed_step_id"
            ),
        "dry_run_only":
            execution_plan.get(
                "dry_run_only"
            ),
    }

    fields = {
        "action_status": (
            predicted.get(
                "expected_action_status"
            )
            == observed["action_status"]
        ),
        "simulation_status": (
            predicted.get(
                "expected_simulation_status"
            )
            == observed[
                "simulation_status"
            ]
        ),
        "lease_status": (
            predicted.get(
                "expected_lease_status"
            )
            == observed["lease_status"]
        ),
        "rollback_performed": (
            predicted.get(
                "expected_rollback_performed"
            )
            == observed[
                "rollback_performed"
            ]
        ),
        "failed_step_id": (
            predicted.get(
                "expected_failed_step_id"
            )
            == observed[
                "failed_step_id"
            ]
        ),
        "dry_run_only": (
            predicted.get(
                "dry_run_only"
            )
            == observed[
                "dry_run_only"
            ]
        ),
    }

    matched = sum(
        1
        for value in fields.values()
        if value
    )

    total = len(fields)

    mismatched = total - matched

    accuracy = round(
        (
            matched
            / total
            * 100
        )
        if total
        else 0.0,
        2,
    )

    return OutcomeComparisonResult(
        shadow_id=shadow.shadow_id,
        decision_id=shadow.decision_id,
        audit_id=audit.audit_id,
        predicted_outcome=predicted,
        observed_outcome=observed,
        field_results=fields,
        matched_fields=matched,
        mismatched_fields=mismatched,
        accuracy_percent=accuracy,
        overall_match=(
            mismatched == 0
        ),
    )
