from __future__ import annotations

from typing import Any

from app.models.decision import (
    DecisionIntelligenceResult,
    DecisionPriority,
    DecisionStatus,
    EngineeringDecision,
    Recommendation,
    RiskLevel,
    RootCause,
)
from app.models.impact_decision import (
    ImpactDecision,
    ImpactSeverity,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeNode,
)
from app.services.impact_analysis import (
    ImpactAnalysisService,
)
from app.services.root_cause_analysis import (
    RootCauseAnalysisService,
    RootCauseAnalysisResult,
)


SEVERITY_SCORE = {
    ImpactSeverity.INFORMATIONAL: 10.0,
    ImpactSeverity.LOW: 25.0,
    ImpactSeverity.MEDIUM: 50.0,
    ImpactSeverity.HIGH: 75.0,
    ImpactSeverity.CRITICAL: 100.0,
    ImpactSeverity.UNKNOWN: 0.0,
}


PRIORITY_SCORE = {
    DecisionPriority.INFORMATIONAL: 10.0,
    DecisionPriority.LOW: 25.0,
    DecisionPriority.MEDIUM: 50.0,
    DecisionPriority.HIGH: 75.0,
    DecisionPriority.URGENT: 100.0,
}


def _clamp(
    value: float,
) -> float:
    return round(
        max(
            0.0,
            min(
                float(value),
                100.0,
            ),
        ),
        2,
    )


def _risk_from_score(
    score: float,
) -> RiskLevel:
    if score >= 85:
        return RiskLevel.CRITICAL

    if score >= 70:
        return RiskLevel.HIGH

    if score >= 45:
        return RiskLevel.MEDIUM

    if score > 0:
        return RiskLevel.LOW

    return RiskLevel.UNKNOWN


def _priority_from_risk(
    risk: RiskLevel,
) -> DecisionPriority:
    mapping = {
        RiskLevel.CRITICAL:
            DecisionPriority.URGENT,
        RiskLevel.HIGH:
            DecisionPriority.HIGH,
        RiskLevel.MEDIUM:
            DecisionPriority.MEDIUM,
        RiskLevel.LOW:
            DecisionPriority.LOW,
        RiskLevel.HEALTHY:
            DecisionPriority.INFORMATIONAL,
        RiskLevel.UNKNOWN:
            DecisionPriority.LOW,
    }

    return mapping.get(
        risk,
        DecisionPriority.LOW,
    )


class DecisionFusionService:
    """
    Fuse impact analysis and root-cause analysis into one explainable
    engineering decision.

    The service performs no network I/O and does not mutate the graph.
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
                "DecisionFusionService requires "
                "a GraphSnapshot"
            )

        self.graph = graph

        self.impact_service = (
            ImpactAnalysisService(
                graph
            )
        )

        self.root_cause_service = (
            RootCauseAnalysisService(
                graph
            )
        )

    def _source(
        self,
        node_id: str,
    ) -> KnowledgeNode:
        return (
            self.impact_service
            .query
            .node(node_id)
        )

    @staticmethod
    def _root_cause_fusion_score(
        cause: RootCause,
    ) -> float:
        """
        Prioritize specific telemetry-backed causes over generic
        availability or impact-description causes.

        RootCause.rank_score remains untouched; this score is used only
        when selecting the primary cause in the fusion layer.
        """

        cause_id = cause.cause_id.lower()

        specificity_bonus = 0.0

        if cause_id.startswith(
            "cause:power:"
        ):
            specificity_bonus = 30.0

        elif cause_id.startswith(
            "cause:upstream:"
        ):
            specificity_bonus = 22.0

        elif cause_id.startswith(
            "cause:interface:"
        ):
            specificity_bonus = 20.0

        elif cause_id.startswith(
            "cause:routing:"
        ):
            specificity_bonus = 18.0

        elif cause_id.startswith(
            "cause:availability:"
        ):
            specificity_bonus = 5.0

        elif cause_id.startswith(
            "impact-cause:"
        ):
            specificity_bonus = -20.0

        evidence_bonus = min(
            len(cause.evidence) * 0.5,
            5.0,
        )

        return (
            cause.rank_score
            + specificity_bonus
            + evidence_bonus
        )

    @classmethod
    def _deduplicate_root_causes(
        cls,
        values: list[RootCause],
    ) -> list[RootCause]:
        unique: dict[
            str,
            RootCause,
        ] = {}

        for item in values:
            current = unique.get(
                item.cause_id
            )

            if (
                current is None
                or cls._root_cause_fusion_score(
                    item
                )
                > cls._root_cause_fusion_score(
                    current
                )
            ):
                unique[item.cause_id] = item

        return sorted(
            unique.values(),
            key=cls._root_cause_fusion_score,
            reverse=True,
        )

    @staticmethod
    def _deduplicate_recommendations(
        values: list[Recommendation],
    ) -> list[Recommendation]:
        unique: dict[
            str,
            Recommendation,
        ] = {}

        for item in values:
            current = unique.get(
                item.recommendation_id
            )

            if current is None:
                unique[
                    item.recommendation_id
                ] = item
                continue

            current_score = (
                PRIORITY_SCORE.get(
                    current.priority,
                    0.0,
                )
                + current.confidence_percent
            )

            item_score = (
                PRIORITY_SCORE.get(
                    item.priority,
                    0.0,
                )
                + item.confidence_percent
            )

            if item_score > current_score:
                unique[
                    item.recommendation_id
                ] = item

        return sorted(
            unique.values(),
            key=lambda item: (
                PRIORITY_SCORE.get(
                    item.priority,
                    0.0,
                ),
                item.confidence_percent,
            ),
            reverse=True,
        )

    def calculate_fused_risk_score(
        self,
        impact: ImpactDecision,
        root_analysis: RootCauseAnalysisResult,
    ) -> float:
        impact_score = (
            SEVERITY_SCORE.get(
                impact.severity,
                0.0,
            )
        )

        cause_score = (
            root_analysis
            .primary_root_cause
            .rank_score
            if (
                root_analysis
                .primary_root_cause
                is not None
            )
            else 0.0
        )

        spof_score = (
            root_analysis.spof.score
        )

        affected_bonus = min(
            impact.affected_count * 2.5,
            15.0,
        )

        backup_reduction = (
            12.0
            if impact.backup_available
            else 0.0
        )

        fused = (
            impact_score * 0.40
            + cause_score * 0.30
            + spof_score * 0.20
            + affected_bonus
            - backup_reduction
        )

        return _clamp(fused)

    def calculate_fused_confidence(
        self,
        impact: ImpactDecision,
        root_analysis: RootCauseAnalysisResult,
    ) -> float:
        root_cause = (
            root_analysis
            .primary_root_cause
        )

        root_confidence = (
            root_cause.confidence_percent
            if root_cause
            else 0.0
        )

        graph_evidence_bonus = min(
            len(root_analysis.evidence)
            * 1.5,
            12.0,
        )

        return _clamp(
            impact.confidence_percent
            * 0.55
            + root_confidence
            * 0.35
            + graph_evidence_bonus
        )

    def build_engineering_decision(
        self,
        source: KnowledgeNode,
        impact: ImpactDecision,
        root_analysis: RootCauseAnalysisResult,
        recommendations: list[
            Recommendation
        ],
        *,
        risk_level: RiskLevel,
        confidence: float,
    ) -> EngineeringDecision:
        primary_cause = (
            root_analysis
            .primary_root_cause
        )

        primary_recommendation = (
            recommendations[0]
            if recommendations
            else None
        )

        if primary_recommendation:
            action = (
                primary_recommendation
                .action
            )

            title = (
                primary_recommendation
                .title
            )

            expected_impact = (
                primary_recommendation
                .expected_impact
            )

            requires_approval = (
                primary_recommendation
                .requires_approval
            )

            interface_name = (
                primary_recommendation
                .interface_name
            )
        else:
            action = (
                "Investigate the source node, "
                "its upstream path and all "
                "critical interfaces."
            )

            title = (
                "Investigate network impact"
            )

            expected_impact = (
                "Identify and restore the "
                "affected service path."
            )

            requires_approval = False
            interface_name = None

        reason_parts = []

        if primary_cause:
            reason_parts.append(
                primary_cause.title
            )

        reason_parts.append(
            f"{impact.affected_count} "
            "dependent entities affected"
        )

        if (
            root_analysis.spof
            .is_single_point_of_failure
        ):
            reason_parts.append(
                "source is a single point "
                "of failure"
            )

        if impact.backup_available:
            reason_parts.append(
                "active backup is available"
            )
        else:
            reason_parts.append(
                "no active backup detected"
            )

        reason = ". ".join(
            reason_parts
        ) + "."

        cause_ids = [
            item.cause_id
            for item
            in root_analysis.root_causes
        ]

        priority = _priority_from_risk(
            risk_level
        )

        return EngineeringDecision(
            decision_id=(
                f"fused-decision:{source.id}"
            ),
            title=title,
            action=action,
            reason=reason,
            priority=priority,
            status=DecisionStatus.PROPOSED,
            confidence_percent=confidence,
            expected_impact=
                expected_impact,
            rollback_plan=(
                "Restore the previous network "
                "state if the action increases "
                "packet loss, latency or service "
                "unavailability."
            ),
            interface_name=
                interface_name,
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            related_cause_ids=
                cause_ids,
            requires_approval=
                requires_approval,
        )

    def build_executive_summary(
        self,
        source: KnowledgeNode,
        impact: ImpactDecision,
        root_analysis: RootCauseAnalysisResult,
        *,
        risk_level: RiskLevel,
        risk_score: float,
    ) -> str:
        cause = (
            root_analysis
            .primary_root_cause
        )

        cause_title = (
            cause.title
            if cause
            else "No confirmed root cause"
        )

        spof_text = (
            "The node is a single point "
            "of failure."
            if (
                root_analysis.spof
                .is_single_point_of_failure
            )
            else (
                "The node is not currently "
                "classified as a single "
                "point of failure."
            )
        )

        backup_text = (
            "An active backup is available."
            if impact.backup_available
            else "No active backup is available."
        )

        return (
            f"{source.label}: "
            f"{impact.affected_count} dependent "
            f"entities may be affected. "
            f"Primary probable cause: "
            f"{cause_title}. "
            f"Risk is {risk_level.value} "
            f"({risk_score:.2f}/100). "
            f"{spof_text} "
            f"{backup_text}"
        )

    def analyze(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> DecisionIntelligenceResult:
        if max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        source = self._source(
            node_id
        )

        impact_result = (
            self.impact_service
            .analyze_node(
                node_id,
                max_depth=max_depth,
            )
        )

        root_result = (
            self.root_cause_service
            .analyze(
                node_id,
                max_depth=max_depth,
            )
        )

        if not impact_result.decisions:
            raise RuntimeError(
                "Impact analysis returned "
                "no decisions"
            )

        impact = (
            impact_result.decisions[0]
        )

        root_causes = (
            self._deduplicate_root_causes(
                [
                    *impact.root_causes,
                    *root_result.root_causes,
                ]
            )
        )

        recommendations = (
            self._deduplicate_recommendations(
                list(
                    impact.recommendations
                )
            )
        )

        risk_score = (
            self.calculate_fused_risk_score(
                impact,
                root_result,
            )
        )

        risk_level = _risk_from_score(
            risk_score
        )

        confidence = (
            self.calculate_fused_confidence(
                impact,
                root_result,
            )
        )

        decision = (
            self.build_engineering_decision(
                source,
                impact,
                root_result,
                recommendations,
                risk_level=risk_level,
                confidence=confidence,
            )
        )

        executive_summary = (
            self.build_executive_summary(
                source,
                impact,
                root_result,
                risk_level=risk_level,
                risk_score=risk_score,
            )
        )

        router_ip = str(
            source.metadata.get(
                "router_ip"
            )
            or source.external_id
            or source.id
        )

        return DecisionIntelligenceResult(
            router_ip=router_ip,
            device_name=source.label,
            engine_name=(
                "SS4TS Knowledge Graph "
                "Decision Fusion Engine"
            ),
            engine_version="1.0",
            risk_level=risk_level,
            risk_score=risk_score,
            executive_summary=
                executive_summary,
            signals=[],
            root_causes=
                root_causes,
            recommendations=
                recommendations,
            decisions=[
                decision,
            ],
            analysis_context={
                "source_node_id":
                    source.id,
                "source_type":
                    source.type.value,
                "source_active":
                    source.active,
                "max_depth":
                    max_depth,
                "affected_count":
                    impact.affected_count,
                "affected_node_ids":
                    impact.affected_node_ids,
                "impact_severity":
                    impact.severity.value,
                "impact_confidence":
                    impact.confidence_percent,
                "spof": (
                    root_result
                    .spof
                    .to_dict()
                ),
                "backup_available":
                    impact.backup_available,
                "fused_confidence":
                    confidence,
            },
            data_sources={
                "knowledge_graph": True,
                "impact_analysis": True,
                "root_cause_analysis": True,
            },
            metadata={
                "fusion_mode":
                    "impact-root-cause",
                "graph_node_count":
                    self.graph.node_count,
                "graph_edge_count":
                    self.graph.edge_count,
                "primary_impact_decision_id":
                    impact.decision_id,
            },
        )


def fuse_graph_decision(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> DecisionIntelligenceResult:
    return DecisionFusionService(
        graph
    ).analyze(
        node_id,
        max_depth=max_depth,
    )
