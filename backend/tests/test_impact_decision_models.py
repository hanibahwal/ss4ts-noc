from __future__ import annotations

import pytest

from app.models.decision import (
    DecisionPriority,
    Evidence,
    Recommendation,
    RecommendationType,
    RootCause,
)
from app.models.impact_decision import (
    AffectedEntity,
    AffectedEntityType,
    ImpactAnalysisResult,
    ImpactDecision,
    ImpactSeverity,
    normalize_impact_decisions,
)
from app.models.knowledge_graph import (
    ImpactPath,
)


def make_decision() -> ImpactDecision:
    return ImpactDecision(
        decision_id="impact:core",
        source_node_id="device:core",
        title="Core device impact",
        summary=(
            "Failure affects downstream devices"
        ),
        severity=ImpactSeverity.CRITICAL,
        priority=DecisionPriority.URGENT,
        confidence_percent=94,
        affected_entities=[
            AffectedEntity(
                node_id="device:branch",
                label="Branch Router",
                entity_type=(
                    AffectedEntityType.DEVICE
                ),
                severity=ImpactSeverity.HIGH,
                impact_score=90,
            ),
            AffectedEntity(
                node_id="service:customer-1",
                label="Customer Service",
                entity_type=(
                    AffectedEntityType
                    .CUSTOMER_SERVICE
                ),
                severity=(
                    ImpactSeverity.CRITICAL
                ),
                impact_score=100,
            ),
        ],
        impact_paths=[
            ImpactPath(
                source_id="device:core",
                target_id="device:branch",
                node_ids=[
                    "device:core",
                    "device:branch",
                ],
                edge_ids=[
                    "edge:core-branch",
                ],
            ),
        ],
        evidence=[
            Evidence(
                key="oper_status",
                value="down",
            ),
        ],
        root_causes=[
            RootCause(
                cause_id="cause:core-down",
                title="Core unavailable",
                description=(
                    "Core device is offline"
                ),
                confidence_percent=95,
                probability_percent=90,
            ),
        ],
        recommendations=[
            Recommendation(
                recommendation_id=(
                    "recommendation:failover"
                ),
                title="Activate backup",
                action=(
                    "Move traffic to backup link"
                ),
                recommendation_type=(
                    RecommendationType.FAILOVER
                ),
                priority=(
                    DecisionPriority.URGENT
                ),
                confidence_percent=93,
            ),
        ],
        backup_available=True,
    )


def test_affected_entity_serialization() -> None:
    entity = AffectedEntity(
        node_id="device:1",
        label="Router 1",
        entity_type="router",
        severity="major",
        impact_score=150,
    )

    result = entity.to_dict()

    assert result["entity_type"] == "device"
    assert result["severity"] == "high"
    assert result["impact_score"] == 100.0


def test_affected_entity_rejects_empty_id() -> None:
    with pytest.raises(
        ValueError,
        match="node_id",
    ):
        AffectedEntity(
            node_id="",
            label="Device",
        )


def test_impact_decision_properties() -> None:
    decision = make_decision()

    assert decision.affected_count == 2

    assert decision.affected_node_ids == [
        "device:branch",
        "service:customer-1",
    ]

    assert (
        decision.highest_impact_score
        == 100.0
    )

    assert (
        decision.primary_root_cause
        is not None
    )

    assert (
        decision.primary_recommendation
        is not None
    )


def test_impact_decision_serialization() -> None:
    result = make_decision().to_dict()

    assert result["severity"] == "critical"
    assert result["priority"] == "urgent"
    assert result["affected_count"] == 2
    assert result["backup_available"] is True

    assert (
        result["primary_root_cause"]
        ["id"]
        == "cause:core-down"
    )

    assert (
        result["primary_recommendation"]
        ["id"]
        == "recommendation:failover"
    )


def test_impact_decision_from_dict() -> None:
    decision = ImpactDecision.from_dict({
        "id": "impact:1",
        "source": "device:1",
        "title": "Impact",
        "description": "Device impact",
        "severity": "critical",
        "priority": "urgent",
        "confidence": 88,
        "affected_nodes": [
            {
                "id": "device:2",
                "name": "Device 2",
                "type": "router",
                "score": 75,
            },
        ],
        "impact_paths": [
            {
                "source": "device:1",
                "target": "device:2",
                "nodes": [
                    "device:1",
                    "device:2",
                ],
                "edges": [
                    "edge:1",
                ],
            },
        ],
        "recommended_actions": [
            {
                "id": "rec:1",
                "title": "Fail over",
                "action": "Use backup",
                "type": "failover",
                "priority": "urgent",
            },
        ],
        "backup_available": "yes",
    })

    assert (
        decision.source_node_id
        == "device:1"
    )
    assert decision.affected_count == 1
    assert decision.backup_available is True
    assert len(decision.recommendations) == 1


def test_duplicate_affected_nodes_rejected() -> None:
    entity = AffectedEntity(
        node_id="device:2",
        label="Device 2",
    )

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        ImpactDecision(
            decision_id="impact:1",
            source_node_id="device:1",
            title="Impact",
            summary="Summary",
            affected_entities=[
                entity,
                entity,
            ],
        )


def test_impact_path_source_must_match() -> None:
    with pytest.raises(
        ValueError,
        match="source_node_id",
    ):
        ImpactDecision(
            decision_id="impact:1",
            source_node_id="device:1",
            title="Impact",
            summary="Summary",
            impact_paths=[
                ImpactPath(
                    source_id="device:other",
                    target_id="device:2",
                    node_ids=[
                        "device:other",
                        "device:2",
                    ],
                ),
            ],
        )


def test_analysis_result_statistics() -> None:
    result = ImpactAnalysisResult(
        source_node_id="device:core",
        decisions=[
            make_decision(),
        ],
    )

    payload = result.to_dict()

    assert (
        payload["statistics"]
        ["decision_count"]
        == 1
    )

    assert (
        payload["statistics"]
        ["affected_count"]
        == 2
    )

    assert (
        payload["statistics"]
        ["critical_decision_count"]
        == 1
    )


def test_normalize_impact_decisions() -> None:
    decisions = normalize_impact_decisions([
        {
            "id": "impact:1",
            "source": "device:1",
            "title": "Impact",
            "summary": "Summary",
        },
    ])

    assert len(decisions) == 1
    assert isinstance(
        decisions[0],
        ImpactDecision,
    )


def test_normalize_invalid_value() -> None:
    assert (
        normalize_impact_decisions(
            "invalid"
        )
        == []
    )
