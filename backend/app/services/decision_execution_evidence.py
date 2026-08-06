from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.decision_audit import (
    DecisionAuditRecord,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.decision_audit_store import (
    DecisionAuditStore,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from app.services.safe_decision_execution_bridge import (
    SafeDecisionExecutionResult,
)


class DecisionExecutionEvidenceError(RuntimeError):
    """Base error for execution evidence generation."""


class DecisionExecutionEvidenceBindingError(
    DecisionExecutionEvidenceError
):
    """Raised when execution evidence identities do not match."""


class DecisionExecutionEvidenceIntegrityError(
    DecisionExecutionEvidenceError
):
    """Raised when a persisted audit record fails verification."""


@dataclass(slots=True)
class DecisionExecutionEvidenceBundle:
    audit: DecisionAuditRecord
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit":
                self.audit.to_dict(),
            "verified":
                self.verified,
            "integrity": {
                "checksum":
                    self.audit.checksum,
                "checksum_algorithm":
                    "sha256",
                "status": (
                    "valid"
                    if self.verified
                    else "corrupted"
                ),
            },
            "safety": {
                "read_only_snapshot": True,
                "lease_token_exposed": False,
                "network_io_performed": False,
                "device_command_executed": False,
            },
        }


class DecisionExecutionEvidenceBuilder:
    """
    Build a tamper-evident evidence snapshot from a completed
    SafeDecisionExecutionResult.

    The evidence is persisted through DecisionAuditStore and protected
    by its SHA-256 checksum. Lease tokens are never included.
    """

    def __init__(
        self,
        *,
        audit_store: DecisionAuditStore,
        authorization_store:
            ExecutionAuthorizationStore,
        lease_store: ExecutionLeaseStore,
    ) -> None:
        if not isinstance(
            audit_store,
            DecisionAuditStore,
        ):
            raise TypeError(
                "audit_store must be a "
                "DecisionAuditStore"
            )

        if not isinstance(
            authorization_store,
            ExecutionAuthorizationStore,
        ):
            raise TypeError(
                "authorization_store must be an "
                "ExecutionAuthorizationStore"
            )

        if not isinstance(
            lease_store,
            ExecutionLeaseStore,
        ):
            raise TypeError(
                "lease_store must be an "
                "ExecutionLeaseStore"
            )

        if (
            authorization_store.database_path.resolve()
            != lease_store.database_path.resolve()
        ):
            raise ValueError(
                "authorization_store and lease_store "
                "must use the same database"
            )

        self.audit_store = audit_store
        self.authorization_store = (
            authorization_store
        )
        self.lease_store = lease_store

    @staticmethod
    def _safe_lease_payload(
        result: SafeDecisionExecutionResult,
    ) -> dict[str, Any]:
        payload = result.lease.to_dict()

        payload.pop(
            "lease_token",
            None,
        )

        payload["token_exposed"] = False

        return payload

    @staticmethod
    def _validate_bindings(
        *,
        result: SafeDecisionExecutionResult,
        plan: ExecutionPlan,
    ) -> None:
        decision_id = (
            result.action.decision_id
        )

        if (
            result.authorization.decision_id
            != decision_id
        ):
            raise DecisionExecutionEvidenceBindingError(
                "Authorization decision_id does not match "
                "DecisionAction decision_id"
            )

        if plan.decision_id != decision_id:
            raise DecisionExecutionEvidenceBindingError(
                "ExecutionPlan decision_id does not match "
                "DecisionAction decision_id"
            )

        if (
            result.authorization.plan_id
            != plan.plan_id
        ):
            raise DecisionExecutionEvidenceBindingError(
                "Authorization plan_id does not match "
                "ExecutionPlan plan_id"
            )

        if (
            result.simulation.plan_id
            != plan.plan_id
        ):
            raise DecisionExecutionEvidenceBindingError(
                "Simulation plan_id does not match "
                "ExecutionPlan plan_id"
            )

        if (
            result.lease.authorization_id
            != result.authorization
            .authorization_id
        ):
            raise DecisionExecutionEvidenceBindingError(
                "Lease authorization_id does not match "
                "execution authorization"
            )

        if (
            result.simulation.source_node_id
            != plan.source_node_id
        ):
            raise DecisionExecutionEvidenceBindingError(
                "Simulation source_node_id does not match "
                "ExecutionPlan source_node_id"
            )

    def build(
        self,
        *,
        result: SafeDecisionExecutionResult,
        plan: ExecutionPlan,
        trace_id: str | None = None,
        created_by: str = (
            "safe-decision-execution-bridge"
        ),
        audit_id: str | None = None,
    ) -> DecisionExecutionEvidenceBundle:
        if not isinstance(
            result,
            SafeDecisionExecutionResult,
        ):
            raise TypeError(
                "result must be a "
                "SafeDecisionExecutionResult"
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan"
            )

        normalized_created_by = str(
            created_by
        ).strip()

        if not normalized_created_by:
            raise ValueError(
                "created_by must not be empty"
            )

        self._validate_bindings(
            result=result,
            plan=plan,
        )

        authorization_events = (
            self.authorization_store.events(
                result.authorization
                .authorization_id
            )
        )

        lease_events = (
            self.lease_store.events(
                result.lease.lease_id
            )
        )

        safe_lease_payload = (
            self._safe_lease_payload(
                result
            )
        )

        resolved_trace_id = (
            str(trace_id).strip()
            if trace_id is not None
            else (
                "execution-trace:"
                + result.action.decision_id
            )
        )

        if not resolved_trace_id:
            raise ValueError(
                "trace_id must not be empty"
            )

        trace_payload = {
            "trace_id":
                resolved_trace_id,
            "decision_id":
                result.action.decision_id,
            "source_node_id":
                plan.source_node_id,
            "title":
                "Safe decision execution evidence",
            "decision_action":
                result.action.to_dict(),
            "final_outcome": {
                "action_status":
                    result.action.status.value,
                "authorization_status":
                    result.authorization
                    .status.value,
                "simulation_status":
                    result.simulation
                    .status.value,
                "lease_status":
                    result.lease.status.value,
            },
            "metadata": {
                "risk_level":
                    result.action
                    .risk_level.value,
                "risk_score":
                    result.action
                    .confidence_percent,
                "primary_cause_id":
                    result.action.incident_id,
            },
        }

        explanation_payload = {
            "approval_authorization":
                result.authorization.to_dict(),
            "authorization_events":
                authorization_events,
            "execution_safety": {
                "approval_required":
                    result.action
                    .approval_required,
                "dry_run_only":
                    plan.dry_run_only,
                "lease_enforced":
                    True,
                "authorization_consumed":
                    result.authorization
                    .consumed,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        }

        execution_plan_payload = (
            plan.to_dict()
        )

        simulation_payload = {
            "simulation":
                result.simulation.to_dict(),
            "released_lease":
                safe_lease_payload,
            "lease_events":
                lease_events,
            "verification_summary": {
                "simulation_completed": (
                    result.simulation
                    .status.value
                    == "completed"
                ),
                "rollback_performed":
                    result.simulation
                    .rollback_performed,
                "failed_step_id":
                    result.simulation
                    .failure_step_id,
                "final_action_status":
                    result.action
                    .status.value,
                "authorization_consumed":
                    result.authorization
                    .consumed,
                "lease_released": (
                    result.lease
                    .status.value
                    == "released"
                ),
            },
        }

        record = self.audit_store.create_record(
            trace=trace_payload,
            explanation=
                explanation_payload,
            execution_plan=
                execution_plan_payload,
            simulation=
                simulation_payload,
            metadata={
                "created_by":
                    normalized_created_by,
                "evidence_bundle":
                    True,
                "authorization_id":
                    result.authorization
                    .authorization_id,
                "lease_id":
                    result.lease.lease_id,
                "lease_token_exposed":
                    False,
            },
            audit_id=audit_id,
        )

        verified = self.audit_store.verify(
            record.audit_id
        )

        if not verified:
            raise (
                DecisionExecutionEvidenceIntegrityError(
                    "Persisted execution evidence "
                    "failed checksum verification"
                )
            )

        return DecisionExecutionEvidenceBundle(
            audit=record,
            verified=True,
        )
