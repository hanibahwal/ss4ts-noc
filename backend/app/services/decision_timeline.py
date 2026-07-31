from __future__ import annotations

from typing import Any

from app.models.decision import (
    DecisionIntelligenceResult,
)
from app.models.decision_timeline import (
    DecisionTimeline,
    DecisionTimelineEvent,
    TimelineEventStatus,
    TimelineEventType,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
)
from app.services.decision_fusion import (
    fuse_graph_decision,
)


class DecisionTimelineBuilder:
    """
    Convert a fused decision result into an ordered,
    explainable network decision story.
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
                "DecisionTimelineBuilder requires "
                "a GraphSnapshot"
            )

        self.graph = graph

    @staticmethod
    def _event(
        *,
        sequence: int,
        event_type: TimelineEventType,
        title: str,
        description: str,
        status: TimelineEventStatus,
        confidence_percent: float,
        source_id: str,
        related_node_ids: list[str] | None = None,
        evidence_ids: list[str] | None = None,
        actionable: bool = False,
        requires_approval: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionTimelineEvent:
        return DecisionTimelineEvent(
            event_id=(
                f"timeline-event:"
                f"{source_id}:"
                f"{sequence}"
            ),
            sequence=sequence,
            event_type=event_type,
            title=title,
            description=description,
            status=status,
            confidence_percent=
                confidence_percent,
            source_id=source_id,
            related_node_ids=(
                related_node_ids or []
            ),
            evidence_ids=(
                evidence_ids or []
            ),
            actionable=actionable,
            requires_approval=
                requires_approval,
            metadata=metadata or {},
        )

    def build_from_result(
        self,
        result: DecisionIntelligenceResult,
    ) -> DecisionTimeline:
        context = result.analysis_context

        source_node_id = str(
            context.get(
                "source_node_id",
                result.router_ip,
            )
        )

        affected_node_ids = [
            str(item)
            for item in context.get(
                "affected_node_ids",
                [],
            )
        ]

        source_active = bool(
            context.get(
                "source_active",
                False,
            )
        )

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

        confidence = float(
            context.get(
                "fused_confidence",
                0.0,
            )
        )

        events: list[
            DecisionTimelineEvent
        ] = []

        events.append(
            self._event(
                sequence=1,
                event_type=(
                    TimelineEventType
                    .OBSERVATION
                ),
                title="Source state observed",
                description=(
                    f"{result.device_name} is "
                    f"{'online' if source_active else 'offline'}."
                ),
                status=(
                    TimelineEventStatus
                    .DETECTED
                ),
                confidence_percent=
                    confidence,
                source_id=source_node_id,
                metadata={
                    "router_ip":
                        result.router_ip,
                    "source_active":
                        source_active,
                    "risk_level":
                        result.risk_level.value,
                    "risk_score":
                        result.risk_score,
                },
            )
        )

        evidence_count = sum(
            len(cause.evidence)
            for cause in result.root_causes
        )

        events.append(
            self._event(
                sequence=2,
                event_type=(
                    TimelineEventType
                    .EVIDENCE
                ),
                title="Evidence collected",
                description=(
                    f"{evidence_count} evidence "
                    "items were collected from "
                    "the Knowledge Graph and "
                    "network telemetry."
                ),
                status=(
                    TimelineEventStatus
                    .CONFIRMED
                ),
                confidence_percent=
                    confidence,
                source_id=source_node_id,
                metadata={
                    "evidence_count":
                        evidence_count,
                    "root_cause_count":
                        len(result.root_causes),
                },
            )
        )

        root_cause = (
            result.primary_root_cause
        )

        if root_cause is not None:
            events.append(
                self._event(
                    sequence=3,
                    event_type=(
                        TimelineEventType
                        .ROOT_CAUSE
                    ),
                    title=(
                        "Primary root cause ranked"
                    ),
                    description=(
                        f"{root_cause.title}. "
                        f"{root_cause.description}"
                    ),
                    status=(
                        TimelineEventStatus
                        .CONFIRMED
                    ),
                    confidence_percent=(
                        root_cause
                        .confidence_percent
                    ),
                    source_id=source_node_id,
                    evidence_ids=[
                        evidence.key
                        for evidence
                        in root_cause.evidence
                    ],
                    metadata={
                        "cause_id":
                            root_cause.cause_id,
                        "category":
                            root_cause
                            .category.value,
                        "probability_percent":
                            root_cause
                            .probability_percent,
                        "rank_score":
                            root_cause.rank_score,
                    },
                )
            )

        affected_count = int(
            context.get(
                "affected_count",
                0,
            )
        )

        events.append(
            self._event(
                sequence=4,
                event_type=(
                    TimelineEventType.IMPACT
                ),
                title="Blast radius calculated",
                description=(
                    f"{affected_count} dependent "
                    "entities may be affected."
                ),
                status=(
                    TimelineEventStatus
                    .CONFIRMED
                ),
                confidence_percent=
                    confidence,
                source_id=source_node_id,
                related_node_ids=
                    affected_node_ids,
                metadata={
                    "affected_count":
                        affected_count,
                    "impact_severity":
                        context.get(
                            "impact_severity"
                        ),
                    "spof": bool(
                        spof.get(
                            "is_single_point_of_failure",
                            False,
                        )
                    ),
                },
            )
        )

        events.append(
            self._event(
                sequence=5,
                event_type=(
                    TimelineEventType.BACKUP
                ),
                title=(
                    "Backup availability checked"
                ),
                description=(
                    "An active backup path is "
                    "available."
                    if backup_available
                    else (
                        "No active backup path "
                        "was detected."
                    )
                ),
                status=(
                    TimelineEventStatus
                    .CONFIRMED
                ),
                confidence_percent=
                    confidence,
                source_id=source_node_id,
                metadata={
                    "backup_available":
                        backup_available,
                    "backup_node_ids":
                        spof.get(
                            "backup_node_ids",
                            [],
                        ),
                    "is_spof":
                        spof.get(
                            "is_single_point_of_failure",
                            False,
                        ),
                },
            )
        )

        recommendation = (
            result.primary_recommendation
        )

        if recommendation is not None:
            events.append(
                self._event(
                    sequence=6,
                    event_type=(
                        TimelineEventType
                        .RECOMMENDATION
                    ),
                    title=(
                        recommendation.title
                    ),
                    description=(
                        recommendation.action
                    ),
                    status=(
                        TimelineEventStatus
                        .PROPOSED
                    ),
                    confidence_percent=(
                        recommendation
                        .confidence_percent
                    ),
                    source_id=source_node_id,
                    actionable=True,
                    requires_approval=(
                        recommendation
                        .requires_approval
                    ),
                    metadata={
                        "recommendation_id":
                            recommendation
                            .recommendation_id,
                        "recommendation_type":
                            recommendation
                            .recommendation_type
                            .value,
                        "priority":
                            recommendation
                            .priority.value,
                        "expected_impact":
                            recommendation
                            .expected_impact,
                    },
                )
            )

        decision = result.primary_decision

        if decision is not None:
            events.append(
                self._event(
                    sequence=7,
                    event_type=(
                        TimelineEventType
                        .DECISION
                    ),
                    title=decision.title,
                    description=(
                        decision.action
                    ),
                    status=(
                        TimelineEventStatus
                        .PROPOSED
                    ),
                    confidence_percent=(
                        decision
                        .confidence_percent
                    ),
                    source_id=source_node_id,
                    actionable=True,
                    requires_approval=(
                        decision
                        .requires_approval
                    ),
                    metadata={
                        "decision_id":
                            decision.decision_id,
                        "priority":
                            decision
                            .priority.value,
                        "decision_status":
                            decision
                            .status.value,
                        "reason":
                            decision.reason,
                        "rollback_plan":
                            decision.rollback_plan,
                    },
                )
            )

        return DecisionTimeline(
            timeline_id=(
                f"decision-timeline:"
                f"{source_node_id}"
            ),
            source_node_id=
                source_node_id,
            title=(
                f"Decision timeline for "
                f"{result.device_name}"
            ),
            events=events,
            decision_id=(
                decision.decision_id
                if decision
                else None
            ),
            explanation=(
                result.executive_summary
            ),
            metadata={
                "router_ip":
                    result.router_ip,
                "device_name":
                    result.device_name,
                "risk_level":
                    result.risk_level.value,
                "risk_score":
                    result.risk_score,
                "engine":
                    result.engine_name,
                "engine_version":
                    result.engine_version,
            },
        )

    def build(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> DecisionTimeline:
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


def build_decision_timeline(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> DecisionTimeline:
    return DecisionTimelineBuilder(
        graph
    ).build(
        node_id,
        max_depth=max_depth,
    )
