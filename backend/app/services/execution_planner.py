from __future__ import annotations

from app.models.decision import (
    DecisionIntelligenceResult,
)
from app.models.execution_plan import (
    ExecutionPlan,
    ExecutionPlanStatus,
    ExecutionPlanStep,
    ExecutionSafetyLevel,
    ExecutionStepStatus,
    ExecutionStepType,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
)
from app.services.decision_fusion import (
    fuse_graph_decision,
)


class ExecutionPlanBuilder:
    """
    Convert a fused engineering decision into a safe execution plan.

    This service only creates dry-run plans. It performs no network I/O
    and does not execute any command on managed devices.
    """

    def __init__(
        self,
        graph: GraphSnapshot,
    ) -> None:
        if not isinstance(
            graph,
            GraphSnapshot,
        ):
            raise TypeError(
                "ExecutionPlanBuilder requires "
                "a GraphSnapshot"
            )

        self.graph = graph

    @staticmethod
    def _step(
        *,
        source_node_id: str,
        sequence: int,
        step_type: ExecutionStepType,
        title: str,
        description: str,
        safety_level: ExecutionSafetyLevel = (
            ExecutionSafetyLevel.READ_ONLY
        ),
        command: str | None = None,
        expected_result: str | None = None,
        rollback_command: str | None = None,
        requires_approval: bool = False,
        reversible: bool = True,
        automatic_allowed: bool = False,
        depends_on: list[str] | None = None,
        verification_step_ids: (
            list[str] | None
        ) = None,
        confidence_percent: float = 0.0,
        estimated_seconds: int = 30,
        metadata: dict | None = None,
    ) -> ExecutionPlanStep:
        return ExecutionPlanStep(
            step_id=(
                f"execution-step:"
                f"{source_node_id}:"
                f"{sequence}"
            ),
            sequence=sequence,
            step_type=step_type,
            title=title,
            description=description,
            status=ExecutionStepStatus.PENDING,
            safety_level=safety_level,
            command=command,
            expected_result=expected_result,
            rollback_command=
                rollback_command,
            timeout_seconds=max(
                estimated_seconds,
                30,
            ),
            estimated_seconds=
                estimated_seconds,
            requires_approval=
                requires_approval,
            reversible=reversible,
            automatic_allowed=
                automatic_allowed,
            depends_on=depends_on or [],
            verification_step_ids=(
                verification_step_ids or []
            ),
            confidence_percent=
                confidence_percent,
            metadata=metadata or {},
        )

    @staticmethod
    def _cause_specific_validation(
        cause_id: str,
    ) -> tuple[str, str]:
        normalized = cause_id.lower()

        if normalized.startswith(
            "cause:power:"
        ):
            return (
                "Validate power condition",
                (
                    "Check utility power, UPS, PoE, "
                    "power supply and voltage telemetry."
                ),
            )

        if normalized.startswith(
            "cause:upstream:"
        ):
            return (
                "Validate upstream dependency",
                (
                    "Check gateway reachability, "
                    "transport link, routing neighbor "
                    "and provider connectivity."
                ),
            )

        if normalized.startswith(
            "cause:interface:"
        ):
            return (
                "Validate failed interface",
                (
                    "Check interface state, errors, "
                    "cabling, optics and remote peer."
                ),
            )

        if normalized.startswith(
            "cause:routing:"
        ):
            return (
                "Validate routing condition",
                (
                    "Check active routes, gateway "
                    "reachability and routing policy."
                ),
            )

        return (
            "Validate primary root cause",
            (
                "Collect current device state and "
                "confirm the highest-ranked cause."
            ),
        )

    @staticmethod
    def _proposed_command(
        result: DecisionIntelligenceResult,
    ) -> str:
        decision = result.primary_decision

        if decision is None:
            return (
                "DRY_RUN_ONLY: investigate "
                "the selected network node"
            )

        return (
            "DRY_RUN_ONLY: "
            f"{decision.action}"
        )

    @staticmethod
    def _rollback_command(
        result: DecisionIntelligenceResult,
    ) -> str:
        decision = result.primary_decision

        if (
            decision is not None
            and decision.rollback_plan
        ):
            return (
                "DRY_RUN_ONLY: "
                f"{decision.rollback_plan}"
            )

        return (
            "DRY_RUN_ONLY: restore the "
            "previous verified network state"
        )

    def build_from_result(
        self,
        result: DecisionIntelligenceResult,
    ) -> ExecutionPlan:
        context = result.analysis_context

        source_node_id = str(
            context.get(
                "source_node_id",
                result.router_ip,
            )
        )

        decision = result.primary_decision
        cause = result.primary_root_cause
        recommendation = (
            result.primary_recommendation
        )

        if decision is None:
            raise RuntimeError(
                "Decision result has no "
                "primary engineering decision"
            )

        cause_id = (
            cause.cause_id
            if cause is not None
            else "cause:unknown"
        )

        (
            validation_title,
            validation_description,
        ) = self._cause_specific_validation(
            cause_id
        )

        confidence = (
            decision.confidence_percent
        )

        approval_required = bool(
            decision.requires_approval
            or (
                recommendation
                is not None
                and recommendation
                .requires_approval
            )
        )

        step_1_id = (
            f"execution-step:"
            f"{source_node_id}:1"
        )

        step_2_id = (
            f"execution-step:"
            f"{source_node_id}:2"
        )

        step_3_id = (
            f"execution-step:"
            f"{source_node_id}:3"
        )

        step_4_id = (
            f"execution-step:"
            f"{source_node_id}:4"
        )

        step_5_id = (
            f"execution-step:"
            f"{source_node_id}:5"
        )

        step_6_id = (
            f"execution-step:"
            f"{source_node_id}:6"
        )

        steps: list[
            ExecutionPlanStep
        ] = []

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=1,
                step_type=(
                    ExecutionStepType.OBSERVE
                ),
                title=(
                    "Capture current network state"
                ),
                description=(
                    "Record current availability, "
                    "risk, interfaces, dependencies "
                    "and routing state."
                ),
                expected_result=(
                    "A current-state snapshot is "
                    "available before any change."
                ),
                automatic_allowed=True,
                confidence_percent=
                    confidence,
                estimated_seconds=15,
                metadata={
                    "router_ip":
                        result.router_ip,
                    "risk_level":
                        result.risk_level.value,
                    "risk_score":
                        result.risk_score,
                },
            )
        )

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=2,
                step_type=(
                    ExecutionStepType.VALIDATE
                ),
                title=validation_title,
                description=(
                    validation_description
                ),
                expected_result=(
                    "The probable cause is either "
                    "confirmed or rejected."
                ),
                automatic_allowed=True,
                depends_on=[
                    step_1_id,
                ],
                confidence_percent=(
                    cause.confidence_percent
                    if cause is not None
                    else confidence
                ),
                estimated_seconds=30,
                metadata={
                    "cause_id":
                        cause_id,
                    "cause_category": (
                        cause.category.value
                        if cause is not None
                        else "unknown"
                    ),
                },
            )
        )

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=3,
                step_type=(
                    ExecutionStepType.VALIDATE
                ),
                title=(
                    "Review blast radius"
                ),
                description=(
                    "Review all affected nodes, "
                    "customer services, SPOF status "
                    "and backup availability."
                ),
                expected_result=(
                    "The engineer understands the "
                    "expected impact before action."
                ),
                automatic_allowed=True,
                depends_on=[
                    step_2_id,
                ],
                confidence_percent=
                    confidence,
                estimated_seconds=20,
                metadata={
                    "affected_count":
                        context.get(
                            "affected_count",
                            0,
                        ),
                    "affected_node_ids":
                        context.get(
                            "affected_node_ids",
                            [],
                        ),
                    "backup_available":
                        context.get(
                            "backup_available",
                            False,
                        ),
                    "spof":
                        context.get(
                            "spof",
                            {},
                        ),
                },
            )
        )

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=4,
                step_type=(
                    ExecutionStepType.APPROVAL
                ),
                title=(
                    "Engineer approval gate"
                ),
                description=(
                    "Review the proposed action, "
                    "expected impact, verification "
                    "method and rollback plan."
                ),
                expected_result=(
                    "The plan is explicitly approved "
                    "or rejected by an engineer."
                ),
                safety_level=(
                    ExecutionSafetyLevel
                    .MEDIUM_RISK
                ),
                requires_approval=True,
                automatic_allowed=False,
                depends_on=[
                    step_3_id,
                ],
                confidence_percent=
                    confidence,
                estimated_seconds=30,
                metadata={
                    "approval_required":
                        approval_required,
                    "decision_id":
                        decision.decision_id,
                },
            )
        )

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=5,
                step_type=(
                    ExecutionStepType.COMMAND
                ),
                title=(
                    "Apply proposed controlled action"
                ),
                description=(
                    "Prepare the selected engineering "
                    "action. Execution remains disabled "
                    "and dry-run only."
                ),
                command=(
                    self._proposed_command(
                        result
                    )
                ),
                expected_result=(
                    decision.expected_impact
                    or (
                        "Network service state "
                        "improves after the action."
                    )
                ),
                rollback_command=(
                    self._rollback_command(
                        result
                    )
                ),
                safety_level=(
                    ExecutionSafetyLevel
                    .MEDIUM_RISK
                ),
                requires_approval=True,
                reversible=True,
                automatic_allowed=False,
                depends_on=[
                    step_4_id,
                ],
                verification_step_ids=[
                    step_6_id,
                ],
                confidence_percent=
                    confidence,
                estimated_seconds=60,
                metadata={
                    "dry_run_only":
                        True,
                    "decision_action":
                        decision.action,
                    "recommendation_id": (
                        recommendation
                        .recommendation_id
                        if recommendation
                        is not None
                        else None
                    ),
                },
            )
        )

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=6,
                step_type=(
                    ExecutionStepType.VERIFY
                ),
                title=(
                    "Verify service restoration"
                ),
                description=(
                    "Recheck availability, packet "
                    "loss, latency, interfaces, routes "
                    "and affected services."
                ),
                expected_result=(
                    "The service is restored without "
                    "new errors or degraded paths."
                ),
                automatic_allowed=True,
                depends_on=[
                    step_5_id,
                ],
                confidence_percent=
                    confidence,
                estimated_seconds=45,
                metadata={
                    "rollback_on_failure":
                        True,
                },
            )
        )

        steps.append(
            self._step(
                source_node_id=
                    source_node_id,
                sequence=7,
                step_type=(
                    ExecutionStepType.NOTIFY
                ),
                title=(
                    "Notify engineer and record outcome"
                ),
                description=(
                    "Publish the plan result, "
                    "verification evidence and "
                    "rollback status."
                ),
                expected_result=(
                    "The incident record contains a "
                    "complete auditable outcome."
                ),
                automatic_allowed=True,
                depends_on=[
                    step_6_id,
                ],
                confidence_percent=
                    confidence,
                estimated_seconds=15,
                metadata={
                    "decision_id":
                        decision.decision_id,
                },
            )
        )

        return ExecutionPlan(
            plan_id=(
                f"execution-plan:"
                f"{source_node_id}"
            ),
            source_node_id=
                source_node_id,
            decision_id=
                decision.decision_id,
            title=(
                f"Safe execution plan for "
                f"{result.device_name}"
            ),
            summary=(
                "Dry-run recovery plan generated "
                "from the fused decision, root cause "
                "and graph impact analysis."
            ),
            steps=steps,
            status=(
                ExecutionPlanStatus
                .PENDING_APPROVAL
            ),
            requires_approval=True,
            approved=False,
            dry_run_only=True,
            automatic_execution_allowed=False,
            metadata={
                "router_ip":
                    result.router_ip,
                "device_name":
                    result.device_name,
                "risk_level":
                    result.risk_level.value,
                "risk_score":
                    result.risk_score,
                "primary_cause_id":
                    cause_id,
                "affected_count":
                    context.get(
                        "affected_count",
                        0,
                    ),
                "backup_available":
                    context.get(
                        "backup_available",
                        False,
                    ),
                "engine":
                    result.engine_name,
                "execution_enabled":
                    False,
            },
        )

    def build(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> ExecutionPlan:
        if max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        result = fuse_graph_decision(
            self.graph,
            node_id,
            max_depth=max_depth,
        )

        return self.build_from_result(
            result
        )


def build_execution_plan(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> ExecutionPlan:
    return ExecutionPlanBuilder(
        graph
    ).build(
        node_id,
        max_depth=max_depth,
    )
