from __future__ import annotations

from typing import Any

from app.models.decision import (
    DecisionIntelligenceResult,
)
from app.models.decision_explanation import (
    DecisionExplanation,
    EvidenceItem,
    ExplanationItem,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
)
from app.services.decision_fusion import (
    fuse_graph_decision,
)


def _value_text(
    value: Any,
) -> str:
    if value is None:
        return "unknown"

    if isinstance(value, bool):
        return (
            "true"
            if value
            else "false"
        )

    return str(value).strip() or "unknown"


class DecisionExplanationService:
    """
    Build an explainable engineering narrative from a fused decision.

    The service performs no network I/O and does not execute commands.
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
                "DecisionExplanationService requires "
                "a GraphSnapshot"
            )

        self.graph = graph

    @staticmethod
    def _evidence_item(
        evidence: Any,
        *,
        source: str,
        confidence: float,
    ) -> EvidenceItem:
        key = getattr(
            evidence,
            "key",
            None,
        )

        value = getattr(
            evidence,
            "value",
            None,
        )

        description = getattr(
            evidence,
            "description",
            None,
        )

        metadata = getattr(
            evidence,
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        return EvidenceItem(
            source=source,
            key=(
                str(key).strip()
                if key is not None
                else "evidence"
            ),
            value=_value_text(
                value
                if value is not None
                else description
            ),
            confidence=confidence,
            metadata=metadata,
        )

    @classmethod
    def _root_cause_explanations(
        cls,
        result: DecisionIntelligenceResult,
    ) -> list[ExplanationItem]:
        explanations: list[
            ExplanationItem
        ] = []

        for index, cause in enumerate(
            result.root_causes,
            start=1,
        ):
            evidence = [
                cls._evidence_item(
                    item,
                    source=(
                        f"root_cause:"
                        f"{cause.cause_id}"
                    ),
                    confidence=(
                        cause.confidence_percent
                    ),
                )
                for item in cause.evidence
            ]

            explanations.append(
                ExplanationItem(
                    title=cause.title,
                    description=(
                        cause.description
                        or (
                            "The decision engine ranked "
                            "this condition as a probable "
                            "cause."
                        )
                    ),
                    confidence=(
                        cause.confidence_percent
                    ),
                    evidence=evidence,
                    metadata={
                        "explanation_type":
                            "root_cause",
                        "cause_id":
                            cause.cause_id,
                        "category":
                            cause.category.value,
                        "rank":
                            index,
                        "rank_score":
                            cause.rank_score,
                        "probability_percent":
                            cause.probability_percent,
                    },
                )
            )

        return explanations

    @staticmethod
    def _impact_explanation(
        result: DecisionIntelligenceResult,
    ) -> ExplanationItem:
        context = result.analysis_context

        affected_count = int(
            context.get(
                "affected_count",
                0,
            )
        )

        affected_node_ids = [
            str(item)
            for item in context.get(
                "affected_node_ids",
                [],
            )
        ]

        confidence = float(
            context.get(
                "impact_confidence",
                context.get(
                    "fused_confidence",
                    0.0,
                ),
            )
        )

        evidence = [
            EvidenceItem(
                source="knowledge_graph",
                key="affected_count",
                value=str(affected_count),
                confidence=confidence,
            ),
            EvidenceItem(
                source="knowledge_graph",
                key="impact_severity",
                value=_value_text(
                    context.get(
                        "impact_severity"
                    )
                ),
                confidence=confidence,
            ),
        ]

        return ExplanationItem(
            title="Blast radius assessment",
            description=(
                f"{affected_count} dependent "
                "entities may be affected by "
                "the source condition."
            ),
            confidence=confidence,
            evidence=evidence,
            metadata={
                "explanation_type":
                    "impact",
                "affected_count":
                    affected_count,
                "affected_node_ids":
                    affected_node_ids,
            },
        )

    @staticmethod
    def _resilience_explanation(
        result: DecisionIntelligenceResult,
    ) -> ExplanationItem:
        context = result.analysis_context

        backup_available = bool(
            context.get(
                "backup_available",
                False,
            )
        )

        spof = context.get(
            "spof",
            {},
        )

        if not isinstance(spof, dict):
            spof = {}

        is_spof = bool(
            spof.get(
                "is_single_point_of_failure",
                False,
            )
        )

        confidence = float(
            context.get(
                "fused_confidence",
                0.0,
            )
        )

        if is_spof and not backup_available:
            description = (
                "The source is classified as a "
                "single point of failure and no "
                "active backup was detected."
            )
        elif backup_available:
            description = (
                "An active backup was detected, "
                "reducing the expected service risk."
            )
        else:
            description = (
                "No active backup was detected, "
                "but the source is not currently "
                "classified as a single point "
                "of failure."
            )

        return ExplanationItem(
            title="Resilience and backup assessment",
            description=description,
            confidence=confidence,
            evidence=[
                EvidenceItem(
                    source="knowledge_graph",
                    key="backup_available",
                    value=_value_text(
                        backup_available
                    ),
                    confidence=confidence,
                ),
                EvidenceItem(
                    source="knowledge_graph",
                    key="single_point_of_failure",
                    value=_value_text(
                        is_spof
                    ),
                    confidence=confidence,
                ),
            ],
            metadata={
                "explanation_type":
                    "resilience",
                "backup_available":
                    backup_available,
                "is_spof":
                    is_spof,
                "spof":
                    spof,
            },
        )

    @staticmethod
    def _decision_explanation(
        result: DecisionIntelligenceResult,
    ) -> ExplanationItem | None:
        decision = result.primary_decision

        if decision is None:
            return None

        evidence = [
            EvidenceItem(
                source="decision_fusion",
                key="priority",
                value=decision.priority.value,
                confidence=(
                    decision.confidence_percent
                ),
            ),
            EvidenceItem(
                source="decision_fusion",
                key="status",
                value=decision.status.value,
                confidence=(
                    decision.confidence_percent
                ),
            ),
        ]

        return ExplanationItem(
            title=decision.title,
            description=(
                f"{decision.reason} "
                f"Proposed action: "
                f"{decision.action}"
            ),
            confidence=(
                decision.confidence_percent
            ),
            evidence=evidence,
            metadata={
                "explanation_type":
                    "decision",
                "decision_id":
                    decision.decision_id,
                "action":
                    decision.action,
                "priority":
                    decision.priority.value,
                "status":
                    decision.status.value,
                "requires_approval":
                    decision.requires_approval,
                "rollback_plan":
                    decision.rollback_plan,
                "expected_impact":
                    decision.expected_impact,
            },
        )

    @staticmethod
    def _recommendations(
        result: DecisionIntelligenceResult,
    ) -> list[str]:
        recommendations: list[str] = []

        for item in result.recommendations:
            value = (
                f"{item.title}: "
                f"{item.action}"
            ).strip()

            if value:
                recommendations.append(
                    value
                )

        return list(
            dict.fromkeys(
                recommendations
            )
        )

    def build_from_result(
        self,
        result: DecisionIntelligenceResult,
    ) -> DecisionExplanation:
        if not isinstance(
            result,
            DecisionIntelligenceResult,
        ):
            raise TypeError(
                "build_from_result requires "
                "a DecisionIntelligenceResult"
            )

        decision = result.primary_decision

        decision_id = (
            decision.decision_id
            if decision is not None
            else (
                f"decision-explanation:"
                f"{result.router_ip}"
            )
        )

        confidence = float(
            result.analysis_context.get(
                "fused_confidence",
                (
                    decision.confidence_percent
                    if decision is not None
                    else 0.0
                ),
            )
        )

        why = (
            self._root_cause_explanations(
                result
            )
        )

        why.append(
            self._impact_explanation(
                result
            )
        )

        why.append(
            self._resilience_explanation(
                result
            )
        )

        decision_item = (
            self._decision_explanation(
                result
            )
        )

        if decision_item is not None:
            why.append(
                decision_item
            )

        primary_cause = (
            result.primary_root_cause
        )

        explanation_order = [
            (
                item.metadata.get(
                    "explanation_type"
                ),
                item.metadata.get(
                    "cause_id"
                ),
                item.title,
            )
            for item in why
        ]

        explanation = DecisionExplanation(
            decision_id=decision_id,
            summary=(
                result.executive_summary
            ),
            confidence=confidence,
            why=why,
            recommendations=(
                self._recommendations(
                    result
                )
            ),
            metadata={
                "router_ip":
                    result.router_ip,
                "device_name":
                    result.device_name,
                "engine_name":
                    result.engine_name,
                "engine_version":
                    result.engine_version,
                "risk_level":
                    result.risk_level.value,
                "risk_score":
                    result.risk_score,
                "primary_cause_id": (
                    primary_cause.cause_id
                    if primary_cause is not None
                    else None
                ),
                "source_node_id":
                    result.analysis_context.get(
                        "source_node_id"
                    ),
                "affected_count":
                    result.analysis_context.get(
                        "affected_count",
                        0,
                    ),
                "backup_available":
                    result.analysis_context.get(
                        "backup_available",
                        False,
                    ),
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        )

        # DecisionExplanation.__post_init__ sorts items by confidence.
        # Restore the causal order produced by Decision Fusion so the
        # selected primary root cause remains the first root-cause item.
        explanation_by_key = {
            (
                item.metadata.get(
                    "explanation_type"
                ),
                item.metadata.get(
                    "cause_id"
                ),
                item.title,
            ): item
            for item in explanation.why
        }

        explanation.why = [
            explanation_by_key[key]
            for key in explanation_order
            if key in explanation_by_key
        ]

        return explanation

    def build(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> DecisionExplanation:
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


def build_decision_explanation(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> DecisionExplanation:
    return DecisionExplanationService(
        graph
    ).build(
        node_id,
        max_depth=max_depth,
    )
