from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.decision import (
    Evidence,
    RiskLevel,
    RootCause,
    SignalCategory,
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


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _boolean(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    normalized = str(value).strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
        "on",
        "up",
        "available",
        "reachable",
        "online",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "down",
        "unavailable",
        "unreachable",
        "offline",
    }:
        return False

    return default


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


@dataclass(slots=True)
class SPOFAssessment:
    node_id: str
    is_single_point_of_failure: bool

    dependent_count: int = 0
    direct_dependent_count: int = 0

    backup_available: bool = False
    backup_node_ids: list[str] = field(
        default_factory=list
    )

    affected_site_count: int = 0
    affected_service_count: int = 0

    score: float = 0.0
    reasons: list[str] = field(
        default_factory=list
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "node_id":
                self.node_id,
            "is_single_point_of_failure":
                self.is_single_point_of_failure,
            "dependent_count":
                self.dependent_count,
            "direct_dependent_count":
                self.direct_dependent_count,
            "backup_available":
                self.backup_available,
            "backup_node_ids":
                list(self.backup_node_ids),
            "affected_site_count":
                self.affected_site_count,
            "affected_service_count":
                self.affected_service_count,
            "score":
                self.score,
            "reasons":
                list(self.reasons),
        }


@dataclass(slots=True)
class RootCauseAnalysisResult:
    source_node_id: str
    root_causes: list[RootCause]

    spof: SPOFAssessment

    evidence: list[Evidence] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.root_causes.sort(
            key=lambda item: (
                item.rank_score
            ),
            reverse=True,
        )

    @property
    def primary_root_cause(
        self,
    ) -> RootCause | None:
        if not self.root_causes:
            return None

        return self.root_causes[0]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        primary = self.primary_root_cause

        return {
            "source_node_id":
                self.source_node_id,
            "cause_count":
                len(self.root_causes),
            "primary_root_cause": (
                primary.to_dict()
                if primary
                else None
            ),
            "root_causes": [
                item.to_dict()
                for item
                in self.root_causes
            ],
            "spof":
                self.spof.to_dict(),
            "evidence": [
                item.to_dict()
                for item
                in self.evidence
            ],
            "metadata":
                dict(self.metadata),
        }


class RootCauseAnalysisService:
    """
    Rank probable network root causes and detect graph-based SPOFs.

    The service is deterministic, performs no network I/O and does not
    mutate the supplied GraphSnapshot.
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
                "RootCauseAnalysisService requires "
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

    def _backups(
        self,
        node_id: str,
    ) -> list[KnowledgeNode]:
        result: dict[
            str,
            KnowledgeNode,
        ] = {}

        for direction in (
            "incoming",
            "outgoing",
        ):
            nodes = self.query.neighbors(
                node_id,
                direction=direction,
                relationships={
                    RelationshipType.BACKED_UP_BY,
                },
                include_inactive=True,
            )

            for node in nodes:
                result[node.id] = node

        return list(
            result.values()
        )

    def _interfaces(
        self,
        node_id: str,
    ) -> list[KnowledgeNode]:
        nodes = self.query.neighbors(
            node_id,
            direction="outgoing",
            relationships={
                RelationshipType.CONTAINS,
            },
            include_inactive=True,
        )

        return [
            node
            for node in nodes
            if node.type == NodeType.INTERFACE
        ]

    def _upstream_dependencies(
        self,
        node_id: str,
    ) -> list[KnowledgeNode]:
        """
        Return direct upstream dependencies, including failed nodes.

        Root-cause analysis must inspect inactive dependencies because
        those nodes are often the actual cause of the source failure.
        """

        return self.query.neighbors(
            node_id,
            direction="outgoing",
            relationships={
                RelationshipType.DEPENDS_ON,
            },
            include_inactive=True,
        )

    def _direct_dependents(
        self,
        node_id: str,
    ) -> list[KnowledgeNode]:
        return self.query.dependents(
            node_id,
            recursive=False,
        )

    def collect_graph_evidence(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> list[Evidence]:
        source = self._source(
            node_id
        )

        direct_dependents = (
            self._direct_dependents(
                node_id
            )
        )

        dependents = self.query.dependents(
            node_id,
            recursive=True,
            max_depth=max_depth,
        )

        dependencies = (
            self._upstream_dependencies(
                node_id
            )
        )

        interfaces = self._interfaces(
            node_id
        )

        backups = self._backups(
            node_id
        )

        return [
            Evidence(
                key="source_active",
                value=source.active,
                label="Source availability",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="source_status",
                value=source.status,
                label="Source operational status",
                source="knowledge_graph",
                weight=0.9,
            ),
            Evidence(
                key="direct_dependent_count",
                value=len(direct_dependents),
                label="Direct dependent nodes",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="dependent_count",
                value=len(dependents),
                label="Recursive dependent nodes",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="dependency_count",
                value=len(dependencies),
                label="Direct upstream dependencies",
                source="knowledge_graph",
                weight=0.9,
            ),
            Evidence(
                key="inactive_dependency_ids",
                value=[
                    node.id
                    for node in dependencies
                    if not node.active
                ],
                label="Inactive upstream dependencies",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="interface_count",
                value=len(interfaces),
                label="Contained interfaces",
                source="knowledge_graph",
                weight=0.8,
            ),
            Evidence(
                key="failed_interface_ids",
                value=[
                    node.id
                    for node in interfaces
                    if (
                        not node.active
                        or str(
                            node.status
                        ).lower()
                        in {
                            "down",
                            "offline",
                            "failed",
                        }
                    )
                ],
                label="Failed interfaces",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="backup_node_ids",
                value=[
                    node.id
                    for node in backups
                ],
                label="Configured backup nodes",
                source="knowledge_graph",
                weight=1.0,
            ),
            Evidence(
                key="active_backup_node_ids",
                value=[
                    node.id
                    for node in backups
                    if node.active
                ],
                label="Available backup nodes",
                source="knowledge_graph",
                weight=1.0,
            ),
        ]

    def detect_single_point_of_failure(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> SPOFAssessment:
        source = self._source(
            node_id
        )

        direct_dependents = (
            self._direct_dependents(
                node_id
            )
        )

        dependents = self.query.dependents(
            node_id,
            recursive=True,
            max_depth=max_depth,
        )

        backups = self._backups(
            node_id
        )

        active_backups = [
            node
            for node in backups
            if node.active
        ]

        affected_sites = {
            node.id
            for node in dependents
            if node.type == NodeType.SITE
        }

        affected_services = {
            node.id
            for node in dependents
            if (
                node.type
                == NodeType.CUSTOMER_SERVICE
            )
        }

        score = 0.0
        reasons: list[str] = []

        if direct_dependents:
            score += min(
                len(direct_dependents)
                * 12.0,
                30.0,
            )

            reasons.append(
                f"{len(direct_dependents)} direct "
                "dependent node(s)"
            )

        if dependents:
            score += min(
                len(dependents)
                * 4.0,
                25.0,
            )

        if affected_sites:
            score += min(
                len(affected_sites)
                * 15.0,
                25.0,
            )

            reasons.append(
                f"{len(affected_sites)} site(s) "
                "depend on this node"
            )

        if affected_services:
            score += min(
                len(affected_services)
                * 20.0,
                30.0,
            )

            reasons.append(
                f"{len(affected_services)} customer "
                "service(s) depend on this node"
            )

        if not active_backups:
            score += 25.0

            reasons.append(
                "No active backup relationship"
            )
        else:
            score -= 35.0

            reasons.append(
                "Active backup relationship exists"
            )

        if not source.active:
            score += 10.0

        score = _clamp(score)

        is_spof = (
            bool(direct_dependents)
            and not active_backups
            and score >= 45.0
        )

        return SPOFAssessment(
            node_id=source.id,
            is_single_point_of_failure=
                is_spof,
            dependent_count=
                len(dependents),
            direct_dependent_count=
                len(direct_dependents),
            backup_available=
                bool(active_backups),
            backup_node_ids=[
                node.id
                for node in backups
            ],
            affected_site_count=
                len(affected_sites),
            affected_service_count=
                len(affected_services),
            score=score,
            reasons=reasons,
        )

    def _availability_cause(
        self,
        source: KnowledgeNode,
        evidence: list[Evidence],
        spof: SPOFAssessment,
    ) -> RootCause | None:
        if source.active:
            return None

        confidence = _clamp(
            75.0
            + source.confidence * 20.0
        )

        probability = _clamp(
            80.0
            + (
                10.0
                if spof.dependent_count
                else 0.0
            )
        )

        return RootCause(
            cause_id=(
                f"cause:availability:{source.id}"
            ),
            title=(
                f"{source.label} is unavailable"
            ),
            description=(
                "The graph source node is inactive "
                "or reports an offline operational "
                "state."
            ),
            category=SignalCategory.AVAILABILITY,
            risk=(
                RiskLevel.CRITICAL
                if spof.is_single_point_of_failure
                else RiskLevel.HIGH
            ),
            confidence_percent=confidence,
            probability_percent=probability,
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            evidence=evidence,
            alternative_causes=[
                "Power interruption",
                "Upstream network failure",
                "Hardware failure",
            ],
            recommendation=(
                "Confirm power, reachability and "
                "device operational state."
            ),
        )

    def _upstream_cause(
        self,
        source: KnowledgeNode,
        evidence: list[Evidence],
    ) -> RootCause | None:
        dependencies = (
            self._upstream_dependencies(
                source.id
            )
        )

        failed = [
            node
            for node in dependencies
            if not node.active
        ]

        if not failed:
            return None

        labels = ", ".join(
            node.label
            for node in failed
        )

        confidence = _clamp(
            72.0
            + len(failed) * 7.0
        )

        probability = _clamp(
            78.0
            + len(failed) * 5.0
        )

        return RootCause(
            cause_id=(
                f"cause:upstream:{source.id}"
            ),
            title="Upstream dependency failure",
            description=(
                "One or more upstream dependency "
                f"nodes are unavailable: {labels}."
            ),
            category=SignalCategory.CONNECTIVITY,
            risk=RiskLevel.HIGH,
            confidence_percent=confidence,
            probability_percent=probability,
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            evidence=evidence,
            alternative_causes=[
                "Routing failure",
                "Transport link failure",
                "Provider outage",
            ],
            recommendation=(
                "Validate upstream links and restore "
                "the failed dependency first."
            ),
        )

    def _interface_cause(
        self,
        source: KnowledgeNode,
        evidence: list[Evidence],
    ) -> RootCause | None:
        interfaces = self._interfaces(
            source.id
        )

        failed = [
            node
            for node in interfaces
            if (
                not node.active
                or str(
                    node.status
                ).lower()
                in {
                    "down",
                    "offline",
                    "failed",
                }
                or _number(
                    node.metadata.get(
                        "total_errors",
                        0,
                    )
                ) > 0
            )
        ]

        if not failed:
            return None

        primary = failed[0]

        total_errors = sum(
            _number(
                node.metadata.get(
                    "total_errors",
                    0,
                )
            )
            for node in failed
        )

        confidence = _clamp(
            60.0
            + len(failed) * 8.0
            + min(
                total_errors / 10.0,
                15.0,
            )
        )

        probability = _clamp(
            62.0
            + len(failed) * 7.0
        )

        return RootCause(
            cause_id=(
                f"cause:interface:{source.id}"
            ),
            title="Interface failure detected",
            description=(
                f"{len(failed)} interface(s) are "
                "down, inactive or reporting errors."
            ),
            category=SignalCategory.INTERFACES,
            risk=_risk_from_score(
                confidence
            ),
            confidence_percent=confidence,
            probability_percent=probability,
            interface_name=
                primary.label,
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            evidence=evidence,
            alternative_causes=[
                "Physical cable failure",
                "Remote peer failure",
                "Port configuration mismatch",
            ],
            recommendation=(
                "Inspect interface state, errors, "
                "cabling and remote peer status."
            ),
        )

    def _power_cause(
        self,
        source: KnowledgeNode,
        evidence: list[Evidence],
    ) -> RootCause | None:
        metadata = source.metadata

        power_status = str(
            metadata.get(
                "power_status",
                "",
            )
        ).strip().lower()

        voltage = _number(
            metadata.get(
                "voltage",
                metadata.get(
                    "voltage_v",
                    0,
                ),
            )
        )

        power_alarm = _boolean(
            metadata.get(
                "power_alarm"
            ),
            False,
        )

        suspected = (
            power_alarm
            or power_status
            in {
                "down",
                "failed",
                "off",
                "lost",
            }
            or (
                voltage > 0
                and voltage < 10.0
            )
        )

        if not suspected:
            return None

        confidence = _clamp(
            88.0
            if power_alarm
            else 78.0
        )

        return RootCause(
            cause_id=(
                f"cause:power:{source.id}"
            ),
            title="Power failure suspected",
            description=(
                "Power telemetry or metadata "
                "indicates loss or abnormal voltage."
            ),
            category=SignalCategory.FAILURE,
            risk=RiskLevel.CRITICAL,
            confidence_percent=confidence,
            probability_percent=90.0,
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            evidence=[
                *evidence,
                Evidence(
                    key="power_status",
                    value=power_status,
                    source="node_metadata",
                    weight=1.0,
                ),
                Evidence(
                    key="voltage",
                    value=voltage,
                    unit="V",
                    source="node_metadata",
                    weight=1.0,
                ),
            ],
            alternative_causes=[
                "UPS failure",
                "Breaker trip",
                "Power adapter failure",
            ],
            recommendation=(
                "Check utility power, UPS, breaker "
                "and device power supply."
            ),
        )

    def _routing_cause(
        self,
        source: KnowledgeNode,
        evidence: list[Evidence],
    ) -> RootCause | None:
        metadata = source.metadata

        route_down = _boolean(
            metadata.get(
                "route_down"
            ),
            False,
        )

        gateway_reachable = _boolean(
            metadata.get(
                "gateway_reachable"
            ),
            True,
        )

        packet_loss = _number(
            metadata.get(
                "packet_loss",
                0,
            )
        )

        suspected = (
            route_down
            or not gateway_reachable
            or packet_loss >= 50.0
        )

        if not suspected:
            return None

        confidence = _clamp(
            65.0
            + (
                15.0
                if route_down
                else 0.0
            )
            + min(
                packet_loss / 5.0,
                15.0,
            )
        )

        probability = _clamp(
            68.0
            + min(
                packet_loss / 4.0,
                20.0,
            )
        )

        return RootCause(
            cause_id=(
                f"cause:routing:{source.id}"
            ),
            title="Routing failure suspected",
            description=(
                "Routing or gateway evidence "
                "indicates loss of reachability."
            ),
            category=SignalCategory.ROUTING,
            risk=_risk_from_score(
                confidence
            ),
            confidence_percent=confidence,
            probability_percent=probability,
            device_ip=(
                source.metadata.get(
                    "router_ip"
                )
                or source.external_id
            ),
            evidence=[
                *evidence,
                Evidence(
                    key="route_down",
                    value=route_down,
                    source="node_metadata",
                    weight=1.0,
                ),
                Evidence(
                    key="gateway_reachable",
                    value=gateway_reachable,
                    source="node_metadata",
                    weight=1.0,
                ),
                Evidence(
                    key="packet_loss",
                    value=packet_loss,
                    unit="percent",
                    source="node_metadata",
                    weight=0.9,
                ),
            ],
            alternative_causes=[
                "Gateway failure",
                "Provider outage",
                "Incorrect route configuration",
            ],
            recommendation=(
                "Validate gateway reachability, "
                "routing table and upstream path."
            ),
        )

    def rank_root_causes(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> list[RootCause]:
        source = self._source(
            node_id
        )

        evidence = (
            self.collect_graph_evidence(
                node_id,
                max_depth=max_depth,
            )
        )

        spof = (
            self.detect_single_point_of_failure(
                node_id,
                max_depth=max_depth,
            )
        )

        candidates = [
            self._power_cause(
                source,
                evidence,
            ),
            self._upstream_cause(
                source,
                evidence,
            ),
            self._interface_cause(
                source,
                evidence,
            ),
            self._routing_cause(
                source,
                evidence,
            ),
            self._availability_cause(
                source,
                evidence,
                spof,
            ),
        ]

        causes = [
            cause
            for cause in candidates
            if cause is not None
        ]

        if not causes:
            causes.append(
                RootCause(
                    cause_id=(
                        f"cause:predictive:"
                        f"{source.id}"
                    ),
                    title=(
                        "No confirmed active fault"
                    ),
                    description=(
                        "The graph currently contains "
                        "insufficient evidence for a "
                        "confirmed root cause."
                    ),
                    category=(
                        SignalCategory.ROOT_CAUSE
                    ),
                    risk=RiskLevel.LOW,
                    confidence_percent=40.0,
                    probability_percent=30.0,
                    device_ip=(
                        source.metadata.get(
                            "router_ip"
                        )
                        or source.external_id
                    ),
                    evidence=evidence,
                    alternative_causes=[
                        "Intermittent connectivity",
                        "Telemetry delay",
                        "Undetected upstream fault",
                    ],
                    recommendation=(
                        "Continue monitoring and "
                        "collect additional telemetry."
                    ),
                )
            )

        return sorted(
            causes,
            key=lambda item: (
                item.rank_score
            ),
            reverse=True,
        )

    def analyze(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
    ) -> RootCauseAnalysisResult:
        if max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        source = self._source(
            node_id
        )

        evidence = (
            self.collect_graph_evidence(
                node_id,
                max_depth=max_depth,
            )
        )

        spof = (
            self.detect_single_point_of_failure(
                node_id,
                max_depth=max_depth,
            )
        )

        causes = self.rank_root_causes(
            node_id,
            max_depth=max_depth,
        )

        return RootCauseAnalysisResult(
            source_node_id=source.id,
            root_causes=causes,
            spof=spof,
            evidence=evidence,
            metadata={
                "source_label":
                    source.label,
                "source_type":
                    source.type.value,
                "source_active":
                    source.active,
                "graph_node_count":
                    self.graph.node_count,
                "graph_edge_count":
                    self.graph.edge_count,
                "max_depth":
                    max_depth,
            },
        )


def analyze_root_causes(
    graph: GraphSnapshot,
    node_id: str,
    *,
    max_depth: int = 10,
) -> RootCauseAnalysisResult:
    return RootCauseAnalysisService(
        graph
    ).analyze(
        node_id,
        max_depth=max_depth,
    )


def analyze_root_cause_summary(
    graph: GraphSnapshot,
    node_id: str,
) -> dict[str, Any]:
    """
    H24.1.2 Public Root Cause Analysis Summary Contract.

    Provides a stable API-friendly response without changing
    the internal RootCauseAnalysisResult model.
    """

    result = analyze_root_causes(
        graph=graph,
        node_id=node_id,
    )

    primary = result.primary_root_cause

    return {
        "node_id": result.source_node_id,
        "status": "completed",
        "root_cause_count": len(result.root_causes),
        "primary_root_cause": (
            primary.to_dict()
            if primary
            else None
        ),
        "root_causes": [
            item.to_dict()
            for item in result.root_causes
        ],
        "spof": result.spof.to_dict(),
        "confidence": (
            primary.confidence_percent
            if primary
            else 0
        ),
        "requires_approval": True,
        "metadata": dict(result.metadata),
    }
