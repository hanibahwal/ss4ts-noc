from __future__ import annotations

from collections import Counter
from typing import Any

from app.models.decision import (
    DecisionPriority,
    Evidence,
    Recommendation,
    RecommendationType,
    RootCause,
    RiskLevel,
    SignalCategory,
)
from app.models.impact_decision import (
    AffectedEntity,
    AffectedEntityType,
    ImpactAnalysisResult,
    ImpactDecision,
    ImpactSeverity,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.knowledge_graph_query import (
    KnowledgeGraphQuery,
)


SEVERITY_SCORE = {
    ImpactSeverity.INFORMATIONAL: 10.0,
    ImpactSeverity.LOW: 25.0,
    ImpactSeverity.MEDIUM: 50.0,
    ImpactSeverity.HIGH: 75.0,
    ImpactSeverity.CRITICAL: 100.0,
    ImpactSeverity.UNKNOWN: 0.0,
}


NODE_TYPE_WEIGHTS = {
    NodeType.CUSTOMER_SERVICE: 32.0,
    NodeType.SITE: 28.0,
    NodeType.TOWER: 26.0,
    NodeType.ROUTER: 22.0,
    NodeType.SWITCH: 20.0,
    NodeType.ACCESS_POINT: 17.0,
    NodeType.NETWORK_LINK: 16.0,
    NodeType.INTERFACE: 12.0,
    NodeType.VLAN: 10.0,
    NodeType.ROUTE: 10.0,
    NodeType.DEVICE: 18.0,
    NodeType.UNKNOWN: 8.0,
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


def _affected_entity_type(
    node_type: NodeType,
) -> AffectedEntityType:
    mapping = {
        NodeType.SITE:
            AffectedEntityType.SITE,
        NodeType.DEVICE:
            AffectedEntityType.DEVICE,
        NodeType.ROUTER:
            AffectedEntityType.DEVICE,
        NodeType.SWITCH:
            AffectedEntityType.DEVICE,
        NodeType.ACCESS_POINT:
            AffectedEntityType.DEVICE,
        NodeType.TOWER:
            AffectedEntityType.DEVICE,
        NodeType.INTERFACE:
            AffectedEntityType.INTERFACE,
        NodeType.NETWORK_LINK:
            AffectedEntityType.NETWORK_LINK,
        NodeType.CUSTOMER_SERVICE:
            AffectedEntityType.CUSTOMER_SERVICE,
        NodeType.VLAN:
            AffectedEntityType.VLAN,
        NodeType.ROUTE:
            AffectedEntityType.ROUTE,
    }

    return mapping.get(
        node_type,
        AffectedEntityType.UNKNOWN,
    )


def _risk_level(
    severity: ImpactSeverity,
) -> RiskLevel:
    mapping = {
        ImpactSeverity.CRITICAL:
            RiskLevel.CRITICAL,
        ImpactSeverity.HIGH:
            RiskLevel.HIGH,
        ImpactSeverity.MEDIUM:
            RiskLevel.MEDIUM,
        ImpactSeverity.LOW:
            RiskLevel.LOW,
        ImpactSeverity.INFORMATIONAL:
            RiskLevel.HEALTHY,
        ImpactSeverity.UNKNOWN:
            RiskLevel.UNKNOWN,
    }

    return mapping[severity]


def _decision_priority(
    severity: ImpactSeverity,
) -> DecisionPriority:
    mapping = {
        ImpactSeverity.CRITICAL:
            DecisionPriority.URGENT,
        ImpactSeverity.HIGH:
            DecisionPriority.HIGH,
        ImpactSeverity.MEDIUM:
            DecisionPriority.MEDIUM,
        ImpactSeverity.LOW:
            DecisionPriority.LOW,
        ImpactSeverity.INFORMATIONAL:
            DecisionPriority.INFORMATIONAL,
        ImpactSeverity.UNKNOWN:
            DecisionPriority.LOW,
    }

    return mapping[severity]


class ImpactAnalysisService:
    """
    Convert Knowledge Graph dependency relationships into
    explainable engineering impact decisions.

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
                "ImpactAnalysisService requires "
                "a GraphSnapshot"
            )

        self.graph = graph
        self.query = KnowledgeGraphQuery(
            graph
        )

    def _source(
        self,
        node_id: str,
    ) -> KnowledgeNode:
        return self.query.node(
            node_id
        )

    def _backup_nodes(
        self,
        node_id: str,
    ) -> list[KnowledgeNode]:
        candidates: dict[
            str,
            KnowledgeNode,
        ] = {}

        for direction in (
            "outgoing",
            "incoming",
        ):
            nodes = self.query.neighbors(
                node_id,
                direction=direction,
                relationships={
                    RelationshipType
                    .BACKED_UP_BY,
                },
                include_inactive=True,
            )

            for node in nodes:
                candidates[node.id] = node

        return list(
            candidates.values()
        )

    def detect_backup(
        self,
        node_id: str,
    ) -> tuple[
        bool,
        list[KnowledgeNode],
    ]:
        nodes = self._backup_nodes(
            node_id
        )

        available = any(
            node.active
            for node in nodes
        )

        return available, nodes

    def calculate_impact_score(
        self,
        node: KnowledgeNode,
        *,
        path_depth: int,
        source_active: bool,
    ) -> float:
        base = NODE_TYPE_WEIGHTS.get(
            node.type,
            8.0,
        )

        depth_penalty = min(
            max(
                path_depth - 1,
                0,
            )
            * 7.0,
            35.0,
        )

        status_bonus = (
            10.0
            if node.active
            else 3.0
        )

        source_failure_bonus = (
            15.0
            if not source_active
            else 0.0
        )

        confidence_bonus = (
            node.confidence
            * 10.0
        )

        return _clamp(
            base
            + status_bonus
            + source_failure_bonus
            + confidence_bonus
            - depth_penalty
        )

    def _entity_severity(
        self,
        node: KnowledgeNode,
        impact_score: float,
    ) -> ImpactSeverity:
        if (
            node.type
            == NodeType.CUSTOMER_SERVICE
        ):
            if impact_score >= 70:
                return ImpactSeverity.CRITICAL

            return ImpactSeverity.HIGH

        if node.type in {
            NodeType.SITE,
            NodeType.TOWER,
        }:
            if impact_score >= 75:
                return ImpactSeverity.CRITICAL

            return ImpactSeverity.HIGH

        if impact_score >= 85:
            return ImpactSeverity.CRITICAL

        if impact_score >= 65:
            return ImpactSeverity.HIGH

        if impact_score >= 40:
            return ImpactSeverity.MEDIUM

        if impact_score > 0:
            return ImpactSeverity.LOW

        return ImpactSeverity.UNKNOWN

    def build_affected_entities(
        self,
        node_id: str,
        *,
        max_depth: int,
    ) -> list[AffectedEntity]:
        source = self._source(
            node_id
        )

        affected = self.query.blast_radius(
            node_id,
            max_depth=max_depth,
            include_inactive=True,
        )

        paths = self.query.impact_paths(
            node_id,
            max_depth=max_depth,
        )

        path_depths = {
            path.target_id:
                len(path.edge_ids)
            for path in paths
        }

        entities: list[
            AffectedEntity
        ] = []

        for node in affected:
            depth = path_depths.get(
                node.id,
                1,
            )

            score = (
                self.calculate_impact_score(
                    node,
                    path_depth=depth,
                    source_active=
                        source.active,
                )
            )

            severity = (
                self._entity_severity(
                    node,
                    score,
                )
            )

            entities.append(
                AffectedEntity(
                    node_id=node.id,
                    label=node.label,
                    entity_type=(
                        _affected_entity_type(
                            node.type
                        )
                    ),
                    severity=severity,
                    active=node.active,
                    impact_score=score,
                    reason=(
                        f"Dependency path from "
                        f"{source.label}"
                    ),
                    site=node.site,
                    metadata={
                        "node_type":
                            node.type.value,
                        "status":
                            node.status,
                        "path_depth":
                            depth,
                        "confidence":
                            node.confidence,
                        **dict(node.metadata),
                    },
                )
            )

        return sorted(
            entities,
            key=lambda item: (
                item.impact_score,
                item.node_id,
            ),
            reverse=True,
        )

    def calculate_severity(
        self,
        entities: list[
            AffectedEntity
        ],
        *,
        backup_available: bool,
    ) -> ImpactSeverity:
        if not entities:
            return ImpactSeverity.INFORMATIONAL

        counts = Counter(
            item.entity_type
            for item in entities
        )

        customer_count = counts[
            AffectedEntityType
            .CUSTOMER_SERVICE
        ]

        site_count = counts[
            AffectedEntityType.SITE
        ]

        maximum = max(
            item.impact_score
            for item in entities
        )

        if (
            customer_count >= 1
            or site_count >= 2
            or len(entities) >= 20
            or maximum >= 95
        ):
            severity = (
                ImpactSeverity.CRITICAL
            )
        elif (
            site_count >= 1
            or len(entities) >= 8
            or maximum >= 75
        ):
            severity = ImpactSeverity.HIGH
        elif (
            len(entities) >= 3
            or maximum >= 50
        ):
            severity = ImpactSeverity.MEDIUM
        else:
            severity = ImpactSeverity.LOW

        if (
            backup_available
            and severity
            == ImpactSeverity.CRITICAL
        ):
            return ImpactSeverity.HIGH

        if (
            backup_available
            and severity
            == ImpactSeverity.HIGH
        ):
            return ImpactSeverity.MEDIUM

        return severity

    def calculate_confidence(
        self,
        source: KnowledgeNode,
        entities: list[
            AffectedEntity
        ],
        *,
        path_count: int,
    ) -> float:
        if not entities:
            return _clamp(
                source.confidence
                * 60.0
            )

        average_node_confidence = (
            sum(
                float(
                    entity.metadata.get(
                        "confidence",
                        1.0,
                    )
                )
                for entity in entities
            )
            / len(entities)
        )

        graph_evidence = min(
            path_count * 4.0,
            20.0,
        )

        source_evidence = (
            source.confidence
            * 40.0
        )

        affected_evidence = (
            average_node_confidence
            * 35.0
        )

        status_evidence = (
            15.0
            if not source.active
            else 5.0
        )

        return _clamp(
            source_evidence
            + affected_evidence
            + graph_evidence
            + status_evidence
        )

    def build_evidence(
        self,
        source: KnowledgeNode,
        entities: list[
            AffectedEntity
        ],
        *,
        path_count: int,
        backup_available: bool,
        backup_nodes: list[
            KnowledgeNode
        ],
    ) -> list[Evidence]:
        counts = Counter(
            item.entity_type.value
            for item in entities
        )

        return [
            Evidence(
                key="source_node_id",
                value=source.id,
                label="Source graph node",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="source_active",
                value=source.active,
                label="Source availability",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="affected_count",
                value=len(entities),
                label="Affected entities",
                source="blast_radius",
                weight=1.0,
            ),
            Evidence(
                key="affected_types",
                value=dict(counts),
                label="Affected entity types",
                source="blast_radius",
                weight=0.9,
            ),
            Evidence(
                key="impact_path_count",
                value=path_count,
                label="Impact paths",
                source="impact_paths",
                weight=0.9,
            ),
            Evidence(
                key="backup_available",
                value=backup_available,
                label="Backup availability",
                source="knowledge_graph",
                weight=1.0,
                metadata={
                    "backup_node_ids": [
                        node.id
                        for node
                        in backup_nodes
                    ],
                },
            ),
        ]

    def build_root_cause(
        self,
        source: KnowledgeNode,
        *,
        severity: ImpactSeverity,
        confidence: float,
        evidence: list[Evidence],
    ) -> RootCause:
        source_status = (
            source.status
            or (
                "online"
                if source.active
                else "offline"
            )
        )

        if not source.active:
            title = (
                f"{source.label} is unavailable"
            )

            description = (
                "The source node is inactive and "
                "has downstream dependency impact."
            )
        else:
            title = (
                f"Potential failure of "
                f"{source.label}"
            )

            description = (
                "This is a predictive dependency "
                "impact assessment for the source "
                "node."
            )

        return RootCause(
            cause_id=(
                f"impact-cause:{source.id}"
            ),
            title=title,
            description=description,
            category=(
                SignalCategory.AVAILABILITY
            ),
            risk=_risk_level(severity),
            confidence_percent=confidence,
            probability_percent=(
                95.0
                if not source.active
                else 65.0
            ),
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            evidence=evidence,
            recommendation=(
                "Validate source availability "
                "and dependency health."
            ),
            alternative_causes=[
                "Upstream connectivity failure",
                "Power interruption",
                "Routing or interface failure",
            ],
        )

    def build_recommendations(
        self,
        source: KnowledgeNode,
        *,
        severity: ImpactSeverity,
        confidence: float,
        backup_available: bool,
        backup_nodes: list[
            KnowledgeNode
        ],
        affected_count: int,
    ) -> list[Recommendation]:
        priority = _decision_priority(
            severity
        )

        recommendations: list[
            Recommendation
        ] = []

        if backup_available:
            backup_labels = ", ".join(
                node.label
                for node in backup_nodes
                if node.active
            )

            recommendations.append(
                Recommendation(
                    recommendation_id=(
                        f"impact-failover:"
                        f"{source.id}"
                    ),
                    title="Activate backup path",
                    action=(
                        "Fail over affected traffic "
                        "to the available backup "
                        f"path: {backup_labels}"
                    ),
                    recommendation_type=(
                        RecommendationType
                        .FAILOVER
                    ),
                    priority=priority,
                    reason=(
                        "An active backup relationship "
                        "exists in the Knowledge Graph."
                    ),
                    expected_impact=(
                        "Reduce or eliminate impact "
                        f"to {affected_count} "
                        "dependent entities."
                    ),
                    confidence_percent=
                        confidence,
                    device_ip=(
                        source.metadata.get(
                            "router_ip"
                        )
                        or source.external_id
                    ),
                    related_cause_ids=[
                        f"impact-cause:{source.id}"
                    ],
                    requires_approval=True,
                    is_reversible=True,
                    estimated_minutes=5,
                )
            )
        else:
            recommendations.append(
                Recommendation(
                    recommendation_id=(
                        f"impact-investigate:"
                        f"{source.id}"
                    ),
                    title=(
                        "Investigate source node"
                    ),
                    action=(
                        "Validate power, upstream "
                        "connectivity, routing and "
                        "critical interfaces on "
                        f"{source.label}."
                    ),
                    recommendation_type=(
                        RecommendationType
                        .INVESTIGATE
                    ),
                    priority=priority,
                    reason=(
                        "No active backup relationship "
                        "was found in the graph."
                    ),
                    expected_impact=(
                        "Restore service to "
                        f"{affected_count} affected "
                        "entities."
                    ),
                    confidence_percent=
                        confidence,
                    device_ip=(
                        source.metadata.get(
                            "router_ip"
                        )
                        or source.external_id
                    ),
                    related_cause_ids=[
                        f"impact-cause:{source.id}"
                    ],
                    requires_approval=False,
                    is_reversible=None,
                    estimated_minutes=15,
                )
            )

        if severity in {
            ImpactSeverity.CRITICAL,
            ImpactSeverity.HIGH,
        }:
            recommendations.append(
                Recommendation(
                    recommendation_id=(
                        f"impact-monitor:"
                        f"{source.id}"
                    ),
                    title=(
                        "Increase impact monitoring"
                    ),
                    action=(
                        "Monitor dependent nodes and "
                        "customer services at an "
                        "accelerated interval."
                    ),
                    recommendation_type=(
                        RecommendationType.MONITOR
                    ),
                    priority=(
                        DecisionPriority.HIGH
                    ),
                    reason=(
                        "The calculated blast radius "
                        "is operationally significant."
                    ),
                    expected_impact=(
                        "Improve incident visibility "
                        "and recovery verification."
                    ),
                    confidence_percent=
                        confidence,
                    requires_approval=False,
                    is_reversible=True,
                    estimated_minutes=1,
                )
            )

        return recommendations

    def analyze_node(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> ImpactAnalysisResult:
        if max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        source = self._source(
            node_id
        )

        entities = (
            self.build_affected_entities(
                node_id,
                max_depth=max_depth,
            )
        )

        paths = self.query.impact_paths(
            node_id,
            max_depth=max_depth,
        )

        (
            backup_available,
            backup_nodes,
        ) = self.detect_backup(
            node_id
        )

        severity = self.calculate_severity(
            entities,
            backup_available=
                backup_available,
        )

        confidence = (
            self.calculate_confidence(
                source,
                entities,
                path_count=len(paths),
            )
        )

        evidence = self.build_evidence(
            source,
            entities,
            path_count=len(paths),
            backup_available=
                backup_available,
            backup_nodes=backup_nodes,
        )

        root_cause = self.build_root_cause(
            source,
            severity=severity,
            confidence=confidence,
            evidence=evidence,
        )

        recommendations = (
            self.build_recommendations(
                source,
                severity=severity,
                confidence=confidence,
                backup_available=
                    backup_available,
                backup_nodes=backup_nodes,
                affected_count=
                    len(entities),
            )
        )

        decision = ImpactDecision(
            decision_id=(
                f"impact-decision:{source.id}"
            ),
            source_node_id=source.id,
            title=(
                f"Impact analysis for "
                f"{source.label}"
            ),
            summary=(
                f"{len(entities)} dependent "
                "entities may be affected. "
                f"Severity is {severity.value}."
            ),
            severity=severity,
            priority=(
                _decision_priority(
                    severity
                )
            ),
            confidence_percent=confidence,
            affected_entities=entities,
            impact_paths=paths,
            evidence=evidence,
            root_causes=[
                root_cause,
            ],
            recommendations=
                recommendations,
            backup_available=
                backup_available,
            requires_approval=any(
                item.requires_approval
                for item
                in recommendations
            ),
            metadata={
                "source_type":
                    source.type.value,
                "source_active":
                    source.active,
                "max_depth":
                    max_depth,
                "backup_node_ids": [
                    node.id
                    for node
                    in backup_nodes
                ],
            },
        )

        return ImpactAnalysisResult(
            source_node_id=source.id,
            decisions=[
                decision,
            ],
            metadata={
                "graph_node_count":
                    self.graph.node_count,
                "graph_edge_count":
                    self.graph.edge_count,
                "analysis_mode":
                    "dependency-blast-radius",
            },
        )


def analyze_graph_impact(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> ImpactAnalysisResult:
    return ImpactAnalysisService(
        graph
    ).analyze_node(
        node_id,
        max_depth=max_depth,
    )
