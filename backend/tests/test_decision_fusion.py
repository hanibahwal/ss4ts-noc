from __future__ import annotations

import pytest

from app.models.decision import (
    DecisionIntelligenceResult,
    DecisionPriority,
    DecisionStatus,
    RiskLevel,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.decision_fusion import (
    DecisionFusionService,
    fuse_graph_decision,
)


def make_graph(
    *,
    source_active: bool = False,
    with_backup: bool = False,
    upstream_failed: bool = False,
    power_alarm: bool = False,
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
                "power_alarm":
                    power_alarm,
            },
        ),
        KnowledgeNode(
            id="device:upstream",
            type=NodeType.ROUTER,
            label="Upstream Router",
            active=not upstream_failed,
            status=(
                "offline"
                if upstream_failed
                else "online"
            ),
        ),
        KnowledgeNode(
            id="device:distribution",
            type=NodeType.SWITCH,
            label="Distribution Switch",
        ),
        KnowledgeNode(
            id="site:branch",
            type=NodeType.SITE,
            label="Branch Site",
        ),
        KnowledgeNode(
            id="service:customer",
            type=NodeType.CUSTOMER_SERVICE,
            label="Customer Service",
        ),
        KnowledgeNode(
            id="device:backup",
            type=NodeType.ROUTER,
            label="Backup Router",
            active=True,
        ),
    ]

    edges = [
        KnowledgeEdge(
            id="edge:core-upstream",
            source_id="device:core",
            target_id="device:upstream",
            type=RelationshipType.DEPENDS_ON,
        ),
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


def test_fusion_returns_decision_result() -> None:
    result = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    assert isinstance(
        result,
        DecisionIntelligenceResult,
    )

    assert result.device_name == "Core Router"
    assert result.router_ip == "10.0.0.1"


def test_fusion_builds_primary_decision() -> None:
    result = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    decision = result.primary_decision

    assert decision is not None
    assert (
        decision.status
        == DecisionStatus.PROPOSED
    )
    assert decision.action


def test_fusion_contains_ranked_root_causes() -> None:
    result = fuse_graph_decision(
        make_graph(
            upstream_failed=True
        ),
        "device:core",
    )

    assert len(result.root_causes) >= 2

    scores = [
        item.rank_score
        for item in result.root_causes
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_fusion_contains_recommendations() -> None:
    result = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    assert result.primary_recommendation is not None
    assert result.recommendations


def test_spof_raises_priority() -> None:
    result = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    decision = result.primary_decision

    assert decision is not None

    assert decision.priority in {
        DecisionPriority.URGENT,
        DecisionPriority.HIGH,
    }

    assert (
        result.analysis_context["spof"]
        ["is_single_point_of_failure"]
        is True
    )


def test_backup_reduces_risk_score() -> None:
    without_backup = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    with_backup = fuse_graph_decision(
        make_graph(
            with_backup=True
        ),
        "device:core",
    )

    assert (
        with_backup.risk_score
        < without_backup.risk_score
    )

    assert (
        with_backup.analysis_context
        ["backup_available"]
        is True
    )


def test_power_alarm_becomes_primary_cause() -> None:
    result = fuse_graph_decision(
        make_graph(
            power_alarm=True
        ),
        "device:core",
    )

    cause = result.primary_root_cause

    assert cause is not None
    assert cause.cause_id.startswith(
        "cause:power:"
    )


def test_result_has_explainable_summary() -> None:
    result = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    assert "dependent entities" in (
        result.executive_summary
    )

    assert "Risk is" in (
        result.executive_summary
    )


def test_result_serializes() -> None:
    result = fuse_graph_decision(
        make_graph(),
        "device:core",
    )

    payload = result.to_dict()

    assert payload["risk"]["score"] >= 0

    assert (
        payload["decisions"][0]["id"]
        == "fused-decision:device:core"
    )

    assert (
        payload["analysis_context"]
        ["source_node_id"]
        == "device:core"
    )


def test_unknown_node_rejected() -> None:
    service = DecisionFusionService(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        service.analyze(
            "device:missing"
        )


def test_invalid_depth_rejected() -> None:
    service = DecisionFusionService(
        make_graph()
    )

    with pytest.raises(
        ValueError,
        match="max_depth",
    ):
        service.analyze(
            "device:core",
            max_depth=0,
        )
