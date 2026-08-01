from __future__ import annotations

from typing import Any

from app.models.decision import (
    DecisionIntelligenceResult,
)
from app.models.decision_trace import (
    DecisionTrace,
    DecisionTraceStage,
    DecisionTraceStageStatus,
    DecisionTraceStageType,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
)
from app.services.decision_explanation import (
    DecisionExplanationService,
)
from app.services.decision_fusion import (
    fuse_graph_decision,
)
from app.services.execution_planner import (
    ExecutionPlanBuilder,
)


class DecisionTraceBuilder:
    """
    Build a read-only audit trace for one engineering decision.

    The trace records how telemetry, graph context, root causes,
    impact, resilience and decision fusion produced the final result.
    No network commands or device I/O are performed.
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
                "DecisionTraceBuilder requires "
                "a GraphSnapshot"
            )

        self.graph = graph

    @staticmethod
    def _unique_text(
        values: list[Any],
    ) -> list[str]:
        return list(
            dict.fromkeys(
                str(value).strip()
                for value in values
                if str(value).strip()
            )
        )

    @staticmethod
    def _stage(
        *,
        source_node_id: str,
        sequence: int,
        stage_type: DecisionTraceStageType,
        title: str,
        description: str,
        confidence_percent: float,
        selected: bool = False,
        input_ids: list[str] | None = None,
        output_ids: list[str] | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionTraceStage:
        return DecisionTraceStage(
            stage_id=(
                f"decision-trace-stage:"
                f"{source_node_id}:"
                f"{sequence}"
            ),
            sequence=sequence,
            stage_type=stage_type,
            title=title,
            description=description,
            status=(
                DecisionTraceStageStatus.SELECTED
                if selected
                else DecisionTraceStageStatus.COMPLETED
            ),
            confidence_percent=
                confidence_percent,
            selected=selected,
            input_ids=input_ids or [],
            output_ids=output_ids or [],
            evidence_ids=evidence_ids or [],
            metadata=metadata or {},
        )

    @staticmethod
    def _confidence(
        result: DecisionIntelligenceResult,
    ) -> float:
        decision = result.primary_decision

        return float(
            result.analysis_context.get(
                "fused_confidence",
                (
                    decision.confidence_percent
                    if decision is not None
                    else 0.0
                ),
            )
        )

    def build_from_result(
        self,
        result: DecisionIntelligenceResult,
    ) -> DecisionTrace:
        if not isinstance(
            result,
            DecisionIntelligenceResult,
        ):
            raise TypeError(
                "build_from_result requires "
                "a DecisionIntelligenceResult"
            )

        context = result.analysis_context

        source_node_id = str(
            context.get(
                "source_node_id",
                result.router_ip,
            )
        )

        decision = result.primary_decision
        primary_cause = result.primary_root_cause
        confidence = self._confidence(result)

        decision_id = (
            decision.decision_id
            if decision is not None
            else (
                f"decision:"
                f"{source_node_id}"
            )
        )

        affected_node_ids = self._unique_text(
            list(
                context.get(
                    "affected_node_ids",
                    [],
                )
            )
        )

        cause_ids = self._unique_text([
            cause.cause_id
            for cause in result.root_causes
        ])

        evidence_ids = self._unique_text([
            (
                f"{cause.cause_id}:"
                f"{evidence.key}"
            )
            for cause in result.root_causes
            for evidence in cause.evidence
        ])

        stages: list[DecisionTraceStage] = []

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=1,
                stage_type=(
                    DecisionTraceStageType.TELEMETRY
                ),
                title="Telemetry state collected",
                description=(
                    "The current device availability "
                    "and operational context were "
                    "collected for analysis."
                ),
                confidence_percent=confidence,
                output_ids=[
                    source_node_id,
                ],
                evidence_ids=[
                    f"telemetry:{source_node_id}",
                ],
                metadata={
                    "router_ip":
                        result.router_ip,
                    "device_name":
                        result.device_name,
                    "source_active":
                        context.get(
                            "source_active"
                        ),
                    "risk_level":
                        result.risk_level.value,
                    "risk_score":
                        result.risk_score,
                },
            )
        )

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=2,
                stage_type=(
                    DecisionTraceStageType.GRAPH_CONTEXT
                ),
                title="Knowledge Graph context resolved",
                description=(
                    "Dependencies, dependents, paths "
                    "and related entities were resolved "
                    "from the Knowledge Graph."
                ),
                confidence_percent=confidence,
                input_ids=[
                    source_node_id,
                ],
                output_ids=affected_node_ids,
                metadata={
                    "graph_node_count":
                        context.get(
                            "graph_node_count",
                            self.graph.node_count,
                        ),
                    "graph_edge_count":
                        context.get(
                            "graph_edge_count",
                            self.graph.edge_count,
                        ),
                    "affected_count":
                        context.get(
                            "affected_count",
                            len(affected_node_ids),
                        ),
                },
            )
        )

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=3,
                stage_type=(
                    DecisionTraceStageType.ROOT_CAUSE
                ),
                title="Root causes ranked",
                description=(
                    f"{len(cause_ids)} root-cause "
                    "candidates were evaluated and "
                    "ranked."
                ),
                confidence_percent=(
                    primary_cause.confidence_percent
                    if primary_cause is not None
                    else confidence
                ),
                selected=(
                    primary_cause is not None
                ),
                input_ids=[
                    source_node_id,
                ],
                output_ids=cause_ids,
                evidence_ids=evidence_ids,
                metadata={
                    "primary_cause_id": (
                        primary_cause.cause_id
                        if primary_cause is not None
                        else None
                    ),
                    "candidate_count":
                        len(cause_ids),
                    "fusion_order_preserved":
                        True,
                },
            )
        )

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=4,
                stage_type=(
                    DecisionTraceStageType.IMPACT
                ),
                title="Blast radius calculated",
                description=(
                    f"{context.get('affected_count', 0)} "
                    "dependent entities may be affected."
                ),
                confidence_percent=float(
                    context.get(
                        "impact_confidence",
                        confidence,
                    )
                ),
                input_ids=[
                    source_node_id,
                ],
                output_ids=affected_node_ids,
                metadata={
                    "affected_count":
                        context.get(
                            "affected_count",
                            0,
                        ),
                    "affected_node_ids":
                        affected_node_ids,
                    "impact_severity":
                        context.get(
                            "impact_severity"
                        ),
                },
            )
        )

        spof = context.get(
            "spof",
            {},
        )

        if not isinstance(spof, dict):
            spof = {}

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=5,
                stage_type=(
                    DecisionTraceStageType.RESILIENCE
                ),
                title="Resilience evaluated",
                description=(
                    "Backup availability and "
                    "single-point-of-failure status "
                    "were evaluated."
                ),
                confidence_percent=confidence,
                input_ids=[
                    source_node_id,
                ],
                output_ids=self._unique_text(
                    list(
                        spof.get(
                            "backup_node_ids",
                            [],
                        )
                    )
                ),
                metadata={
                    "backup_available":
                        context.get(
                            "backup_available",
                            False,
                        ),
                    "is_single_point_of_failure":
                        spof.get(
                            "is_single_point_of_failure",
                            False,
                        ),
                    "spof":
                        spof,
                },
            )
        )

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=6,
                stage_type=(
                    DecisionTraceStageType.DECISION_FUSION
                ),
                title="Engineering decision fused",
                description=(
                    "Root cause, impact, resilience "
                    "and recommendations were fused "
                    "into one engineering decision."
                ),
                confidence_percent=confidence,
                selected=(
                    decision is not None
                ),
                input_ids=cause_ids,
                output_ids=[
                    decision_id,
                ],
                metadata={
                    "decision_id":
                        decision_id,
                    "decision_action": (
                        decision.action
                        if decision is not None
                        else None
                    ),
                    "decision_priority": (
                        decision.priority.value
                        if decision is not None
                        else None
                    ),
                    "requires_approval": (
                        decision.requires_approval
                        if decision is not None
                        else False
                    ),
                },
            )
        )

        explanation = (
            DecisionExplanationService(
                self.graph
            ).build_from_result(
                result
            )
        )

        explanation_ids = [
            (
                item.metadata.get(
                    "cause_id"
                )
                or (
                    f"explanation:"
                    f"{item.metadata.get('explanation_type')}:"
                    f"{index}"
                )
            )
            for index, item in enumerate(
                explanation.why,
                start=1,
            )
        ]

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=7,
                stage_type=(
                    DecisionTraceStageType.EXPLANATION
                ),
                title="Decision explanation generated",
                description=(
                    "A human-readable explanation "
                    "was generated from the selected "
                    "causes, evidence and impact."
                ),
                confidence_percent=
                    explanation.confidence,
                input_ids=[
                    decision_id,
                ],
                output_ids=self._unique_text(
                    explanation_ids
                ),
                metadata={
                    "explanation_item_count":
                        len(explanation.why),
                    "recommendation_count":
                        len(
                            explanation
                            .recommendations
                        ),
                    "primary_cause_id":
                        explanation.metadata.get(
                            "primary_cause_id"
                        ),
                },
            )
        )

        execution_plan = (
            ExecutionPlanBuilder(
                self.graph
            ).build_from_result(
                result
            )
        )

        stages.append(
            self._stage(
                source_node_id=source_node_id,
                sequence=8,
                stage_type=(
                    DecisionTraceStageType.EXECUTION_PLAN
                ),
                title="Safe execution plan generated",
                description=(
                    "A dry-run execution plan with "
                    "approval, verification and rollback "
                    "controls was generated."
                ),
                confidence_percent=confidence,
                input_ids=[
                    decision_id,
                ],
                output_ids=[
                    execution_plan.plan_id,
                ],
                metadata={
                    "plan_id":
                        execution_plan.plan_id,
                    "step_count":
                        execution_plan.step_count,
                    "mutating_step_count":
                        execution_plan
                        .mutating_step_count,
                    "dry_run_only":
                        execution_plan.dry_run_only,
                    "approval_required":
                        execution_plan
                        .approval_required,
                    "rollback_available":
                        execution_plan
                        .rollback_available,
                    "execution_enabled":
                        False,
                },
            )
        )

        return DecisionTrace(
            trace_id=(
                f"decision-trace:"
                f"{source_node_id}"
            ),
            decision_id=decision_id,
            source_node_id=
                source_node_id,
            title=(
                f"Decision trace for "
                f"{result.device_name}"
            ),
            stages=stages,
            read_only=True,
            network_io_performed=False,
            device_command_executed=False,
            metadata={
                "router_ip":
                    result.router_ip,
                "device_name":
                    result.device_name,
                "risk_level":
                    result.risk_level.value,
                "risk_score":
                    result.risk_score,
                "primary_cause_id": (
                    primary_cause.cause_id
                    if primary_cause is not None
                    else None
                ),
                "affected_count":
                    context.get(
                        "affected_count",
                        0,
                    ),
                "engine_name":
                    result.engine_name,
                "engine_version":
                    result.engine_version,
                "trace_version":
                    "1.0",
            },
        )

    def build(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> DecisionTrace:
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


def build_decision_trace(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> DecisionTrace:
    return DecisionTraceBuilder(
        graph
    ).build(
        node_id,
        max_depth=max_depth,
    )
