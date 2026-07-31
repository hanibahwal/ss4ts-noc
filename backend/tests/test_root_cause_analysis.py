from __future__ import annotations

import pytest

from app.models.decision import (
    SignalCategory,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.root_cause_analysis import (
    RootCauseAnalysisResult,
    RootCauseAnalysisService,
    analyze_root_causes,
)


def make_graph(
    *,
    source_active: bool = False,
    with_backup: bool = False,
    upstream_failed: bool = False,
    interface_failed: bool = False,
    power_alarm: bool = False,
    route_down: bool = False,
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
                "route_down":
                    route_down,
                "gateway_reachable":
                    not route_down,
                "packet_loss": (
                    80
                    if route_down
                    else 0
                ),
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
            id="interface:core:1",
            type=NodeType.INTERFACE,
            label="ether1",
            active=not interface_failed,
            status=(
                "down"
                if interface_failed
                else "up"
            ),
            metadata={
                "total_errors": (
                    100
                    if interface_failed
                    else 0
                ),
            },
        ),
        KnowledgeNode(
            id="device:distribution",
            type=NodeType.SWITCH,
            label="Distribution",
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
            id="edge:core-interface",
            source_id="device:core",
            target_id="interface:core:1",
            type=RelationshipType.CONTAINS,
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
            id="edge:service-site",
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


def test_analysis_returns_ranked_result() -> None:
    result = analyze_root_causes(
        make_graph(),
        "device:core",
    )

    assert isinstance(
        result,
        RootCauseAnalysisResult,
    )

    assert result.primary_root_cause is not None

    scores = [
        cause.rank_score
        for cause in result.root_causes
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_offline_source_generates_availability_cause() -> None:
    result = analyze_root_causes(
        make_graph(),
        "device:core",
    )

    assert any(
        cause.category
        == SignalCategory.AVAILABILITY
        for cause in result.root_causes
    )


def test_upstream_failure_is_detected() -> None:
    result = analyze_root_causes(
        make_graph(
            upstream_failed=True
        ),
        "device:core",
    )

    assert any(
        cause.category
        == SignalCategory.CONNECTIVITY
        for cause in result.root_causes
    )


def test_interface_failure_is_detected() -> None:
    result = analyze_root_causes(
        make_graph(
            interface_failed=True
        ),
        "device:core",
    )

    cause = next(
        cause
        for cause in result.root_causes
        if cause.category
        == SignalCategory.INTERFACES
    )

    assert cause.interface_name == "ether1"


def test_power_failure_is_ranked() -> None:
    result = analyze_root_causes(
        make_graph(
            power_alarm=True
        ),
        "device:core",
    )

    power = next(
        cause
        for cause in result.root_causes
        if cause.cause_id.startswith(
            "cause:power:"
        )
    )

    assert power.probability_percent == 90.0


def test_routing_failure_is_detected() -> None:
    result = analyze_root_causes(
        make_graph(
            route_down=True
        ),
        "device:core",
    )

    assert any(
        cause.category
        == SignalCategory.ROUTING
        for cause in result.root_causes
    )


def test_node_without_backup_is_spof() -> None:
    result = analyze_root_causes(
        make_graph(),
        "device:core",
    )

    assert (
        result.spof
        .is_single_point_of_failure
        is True
    )

    assert (
        result.spof
        .affected_service_count
        == 1
    )


def test_active_backup_removes_spof() -> None:
    result = analyze_root_causes(
        make_graph(
            with_backup=True
        ),
        "device:core",
    )

    assert result.spof.backup_available is True

    assert (
        result.spof
        .is_single_point_of_failure
        is False
    )


def test_graph_evidence_contains_failed_interfaces() -> None:
    service = RootCauseAnalysisService(
        make_graph(
            interface_failed=True
        )
    )

    evidence = (
        service.collect_graph_evidence(
            "device:core"
        )
    )

    failed = next(
        item
        for item in evidence
        if item.key
        == "failed_interface_ids"
    )

    assert failed.value == [
        "interface:core:1",
    ]


def test_healthy_isolated_node_uses_predictive_cause() -> None:
    graph = GraphSnapshot(
        nodes=[
            KnowledgeNode(
                id="device:isolated",
                type=NodeType.DEVICE,
                label="Isolated Device",
                active=True,
            ),
        ],
    )

    result = analyze_root_causes(
        graph,
        "device:isolated",
    )

    assert len(result.root_causes) == 1

    assert (
        result.root_causes[0]
        .cause_id
        == "cause:predictive:device:isolated"
    )


def test_unknown_node_rejected() -> None:
    service = RootCauseAnalysisService(
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
    service = RootCauseAnalysisService(
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
