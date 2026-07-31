from __future__ import annotations

import pytest

from app.models.decision import (
    DecisionPriority,
    RecommendationType,
)
from app.models.impact_decision import (
    ImpactAnalysisResult,
    ImpactSeverity,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.impact_analysis import (
    ImpactAnalysisService,
    analyze_graph_impact,
)


def make_graph(
    *,
    source_active: bool = False,
    with_backup: bool = False,
) -> GraphSnapshot:
    nodes = [
        KnowledgeNode(
            id="device:core",
            type=NodeType.ROUTER,
            label="Core Router",
            active=source_active,
            status=(
                "online"
                if source_active
                else "offline"
            ),
            external_id="10.0.0.1",
            confidence=0.98,
            metadata={
                "router_ip": "10.0.0.1",
            },
        ),
        KnowledgeNode(
            id="device:distribution",
            type=NodeType.SWITCH,
            label="Distribution Switch",
            active=True,
            confidence=0.95,
        ),
        KnowledgeNode(
            id="site:branch",
            type=NodeType.SITE,
            label="Branch Site",
            active=True,
            confidence=0.95,
        ),
        KnowledgeNode(
            id="service:customer",
            type=(
                NodeType.CUSTOMER_SERVICE
            ),
            label="Customer Service",
            active=True,
            confidence=0.99,
        ),
        KnowledgeNode(
            id="device:backup",
            type=NodeType.ROUTER,
            label="Backup Router",
            active=True,
            confidence=0.97,
        ),
    ]

    edges = [
        KnowledgeEdge(
            id="edge:distribution-core",
            source_id="device:distribution",
            target_id="device:core",
            type=RelationshipType.DEPENDS_ON,
        ),
        KnowledgeEdge(
            id="edge:site-distribution",
            source_id="site:branch",
            target_id="device:distribution",
            type=RelationshipType.DEPENDS_ON,
        ),
        KnowledgeEdge(
            id="edge:customer-site",
            source_id="service:customer",
            target_id="site:branch",
            type=RelationshipType.DEPENDS_ON,
        ),
    ]

    if with_backup:
        edges.append(
            KnowledgeEdge(
                id="edge:core-backup",
                source_id="device:core",
                target_id="device:backup",
                type=(
                    RelationshipType
                    .BACKED_UP_BY
                ),
            )
        )

    return GraphSnapshot(
        nodes=nodes,
        edges=edges,
    )


def test_analyze_node_returns_result() -> None:
    result = analyze_graph_impact(
        make_graph(),
        "device:core",
    )

    assert isinstance(
        result,
        ImpactAnalysisResult,
    )

    assert result.decision_count == 1
    assert result.affected_count == 3


def test_customer_service_makes_impact_critical() -> None:
    result = analyze_graph_impact(
        make_graph(),
        "device:core",
    )

    decision = result.decisions[0]

    assert (
        decision.severity
        == ImpactSeverity.CRITICAL
    )

    assert (
        decision.priority
        == DecisionPriority.URGENT
    )


def test_analysis_builds_impact_paths() -> None:
    result = analyze_graph_impact(
        make_graph(),
        "device:core",
    )

    decision = result.decisions[0]

    targets = {
        path.target_id
        for path
        in decision.impact_paths
    }

    assert targets == {
        "device:distribution",
        "site:branch",
        "service:customer",
    }


def test_analysis_builds_root_cause() -> None:
    result = analyze_graph_impact(
        make_graph(),
        "device:core",
    )

    cause = (
        result.decisions[0]
        .primary_root_cause
    )

    assert cause is not None
    assert cause.device_ip == "10.0.0.1"
    assert cause.confidence_percent > 0


def test_no_backup_generates_investigation() -> None:
    result = analyze_graph_impact(
        make_graph(),
        "device:core",
    )

    decision = result.decisions[0]

    assert (
        decision.backup_available
        is False
    )

    assert any(
        item.recommendation_type
        == RecommendationType.INVESTIGATE
        for item
        in decision.recommendations
    )


def test_backup_generates_failover() -> None:
    result = analyze_graph_impact(
        make_graph(with_backup=True),
        "device:core",
    )

    decision = result.decisions[0]

    assert (
        decision.backup_available
        is True
    )

    assert any(
        item.recommendation_type
        == RecommendationType.FAILOVER
        for item
        in decision.recommendations
    )


def test_backup_reduces_severity() -> None:
    without_backup = (
        analyze_graph_impact(
            make_graph(),
            "device:core",
        )
        .decisions[0]
    )

    with_backup = (
        analyze_graph_impact(
            make_graph(
                with_backup=True
            ),
            "device:core",
        )
        .decisions[0]
    )

    assert (
        without_backup.severity
        == ImpactSeverity.CRITICAL
    )

    assert (
        with_backup.severity
        == ImpactSeverity.HIGH
    )


def test_affected_entities_are_ranked() -> None:
    result = analyze_graph_impact(
        make_graph(),
        "device:core",
    )

    scores = [
        item.impact_score
        for item
        in result.decisions[0]
        .affected_entities
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_unknown_node_raises_key_error() -> None:
    service = ImpactAnalysisService(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        service.analyze_node(
            "device:missing"
        )


def test_invalid_depth_rejected() -> None:
    service = ImpactAnalysisService(
        make_graph()
    )

    with pytest.raises(
        ValueError,
        match="max_depth",
    ):
        service.analyze_node(
            "device:core",
            max_depth=0,
        )


def test_isolated_node_has_informational_impact() -> None:
    graph = GraphSnapshot(
        nodes=[
            KnowledgeNode(
                id="device:isolated",
                type=NodeType.DEVICE,
                label="Isolated Device",
            ),
        ],
    )

    result = analyze_graph_impact(
        graph,
        "device:isolated",
    )

    decision = result.decisions[0]

    assert decision.affected_count == 0

    assert (
        decision.severity
        == ImpactSeverity.INFORMATIONAL
    )
