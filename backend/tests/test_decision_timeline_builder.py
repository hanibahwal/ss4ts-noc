from __future__ import annotations

import pytest

from app.models.decision_timeline import (
    DecisionTimeline,
    TimelineEventType,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.decision_timeline import (
    DecisionTimelineBuilder,
    build_decision_timeline,
)


def make_graph(
    *,
    source_active: bool = False,
    with_backup: bool = False,
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


def test_builder_returns_timeline() -> None:
    timeline = build_decision_timeline(
        make_graph(),
        "device:core",
    )

    assert isinstance(
        timeline,
        DecisionTimeline,
    )

    assert timeline.source_node_id == "device:core"
    assert timeline.event_count == 7


def test_timeline_event_order() -> None:
    timeline = build_decision_timeline(
        make_graph(),
        "device:core",
    )

    assert [
        event.event_type
        for event in timeline.events
    ] == [
        TimelineEventType.OBSERVATION,
        TimelineEventType.EVIDENCE,
        TimelineEventType.ROOT_CAUSE,
        TimelineEventType.IMPACT,
        TimelineEventType.BACKUP,
        TimelineEventType.RECOMMENDATION,
        TimelineEventType.DECISION,
    ]


def test_power_alarm_is_primary_cause_event() -> None:
    timeline = build_decision_timeline(
        make_graph(
            power_alarm=True
        ),
        "device:core",
    )

    cause_event = next(
        event
        for event in timeline.events
        if (
            event.event_type
            == TimelineEventType.ROOT_CAUSE
        )
    )

    assert (
        cause_event.metadata["cause_id"]
        .startswith("cause:power:")
    )


def test_backup_event_reports_available() -> None:
    timeline = build_decision_timeline(
        make_graph(
            with_backup=True
        ),
        "device:core",
    )

    backup_event = next(
        event
        for event in timeline.events
        if (
            event.event_type
            == TimelineEventType.BACKUP
        )
    )

    assert (
        backup_event.metadata
        ["backup_available"]
        is True
    )


def test_impact_event_contains_affected_nodes() -> None:
    timeline = build_decision_timeline(
        make_graph(),
        "device:core",
    )

    impact_event = next(
        event
        for event in timeline.events
        if (
            event.event_type
            == TimelineEventType.IMPACT
        )
    )

    assert (
        impact_event.metadata
        ["affected_count"]
        == 3
    )

    assert set(
        impact_event.related_node_ids
    ) == {
        "device:distribution",
        "site:branch",
        "service:customer",
    }


def test_decision_is_final_event() -> None:
    timeline = build_decision_timeline(
        make_graph(),
        "device:core",
    )

    assert timeline.final_event is not None

    assert (
        timeline.final_event.event_type
        == TimelineEventType.DECISION
    )

    assert timeline.final_event.actionable is True


def test_timeline_explanation_present() -> None:
    timeline = build_decision_timeline(
        make_graph(),
        "device:core",
    )

    assert timeline.explanation
    assert "dependent entities" in timeline.explanation


def test_invalid_depth_rejected() -> None:
    builder = DecisionTimelineBuilder(
        make_graph()
    )

    with pytest.raises(
        ValueError,
        match="max_depth",
    ):
        builder.build(
            "device:core",
            max_depth=0,
        )


def test_unknown_node_rejected() -> None:
    builder = DecisionTimelineBuilder(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        builder.build(
            "device:missing"
        )
