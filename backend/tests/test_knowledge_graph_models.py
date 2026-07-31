from __future__ import annotations

import pytest

from app.models.knowledge_graph import (
    GraphSnapshot,
    ImpactPath,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
    normalize_graph,
)


def sample_nodes() -> list[KnowledgeNode]:
    return [
        KnowledgeNode(
            id="site:riyadh",
            type=NodeType.SITE,
            label="Riyadh Site",
        ),
        KnowledgeNode(
            id="router:10.0.0.1",
            type=NodeType.ROUTER,
            label="Core Router",
            site="Riyadh",
        ),
        KnowledgeNode(
            id="interface:10.0.0.1:ether1",
            type=NodeType.INTERFACE,
            label="ether1",
        ),
    ]


def sample_edges() -> list[KnowledgeEdge]:
    return [
        KnowledgeEdge(
            id="edge:site-router",
            source_id="site:riyadh",
            target_id="router:10.0.0.1",
            type=RelationshipType.CONTAINS,
        ),
        KnowledgeEdge(
            id="edge:router-interface",
            source_id="router:10.0.0.1",
            target_id="interface:10.0.0.1:ether1",
            type=RelationshipType.CONTAINS,
        ),
    ]


def test_knowledge_node_serialization() -> None:
    node = KnowledgeNode(
        id="router:192.168.1.1",
        type=NodeType.ROUTER,
        label="Main Router",
        confidence=1.5,
        metadata={
            "router_ip": "192.168.1.1",
        },
    )

    result = node.to_dict()

    assert result["id"] == "router:192.168.1.1"
    assert result["type"] == "router"
    assert result["confidence"] == 1.0
    assert result["metadata"]["router_ip"] == "192.168.1.1"


def test_knowledge_node_from_dict_aliases() -> None:
    node = KnowledgeNode.from_dict({
        "node_id": "ap:1",
        "node_type": "ap",
        "name": "Outdoor AP",
        "active": "yes",
    })

    assert node.id == "ap:1"
    assert node.type == NodeType.ACCESS_POINT
    assert node.label == "Outdoor AP"
    assert node.active is True


def test_knowledge_node_rejects_empty_id() -> None:
    with pytest.raises(
        ValueError,
        match="id must not be empty",
    ):
        KnowledgeNode(
            id="",
            type=NodeType.DEVICE,
            label="Device",
        )


def test_knowledge_edge_serialization() -> None:
    edge = KnowledgeEdge(
        id="edge:1",
        source_id="router:1",
        target_id="interface:1",
        type=RelationshipType.CONTAINS,
        confidence=-1,
    )

    result = edge.to_dict()

    assert result["type"] == "contains"
    assert result["confidence"] == 0.0


def test_knowledge_edge_rejects_self_reference() -> None:
    with pytest.raises(
        ValueError,
        match="self-references",
    ):
        KnowledgeEdge(
            id="edge:self",
            source_id="router:1",
            target_id="router:1",
            type=RelationshipType.CONNECTED_TO,
        )


def test_graph_snapshot_counts_and_lookup() -> None:
    graph = GraphSnapshot(
        nodes=sample_nodes(),
        edges=sample_edges(),
    )

    assert graph.node_count == 3
    assert graph.edge_count == 2

    node = graph.get_node(
        "router:10.0.0.1"
    )

    assert node is not None
    assert node.label == "Core Router"

    assert len(
        graph.outgoing_edges(
            "router:10.0.0.1"
        )
    ) == 1

    assert len(
        graph.incoming_edges(
            "router:10.0.0.1"
        )
    ) == 1


def test_graph_snapshot_rejects_duplicate_nodes() -> None:
    node = KnowledgeNode(
        id="router:1",
        type=NodeType.ROUTER,
        label="Router",
    )

    with pytest.raises(
        ValueError,
        match="duplicate node ids",
    ):
        GraphSnapshot(
            nodes=[
                node,
                node,
            ],
        )


def test_graph_snapshot_rejects_unknown_edge_target() -> None:
    with pytest.raises(
        ValueError,
        match="unknown target node",
    ):
        GraphSnapshot(
            nodes=[
                KnowledgeNode(
                    id="router:1",
                    type=NodeType.ROUTER,
                    label="Router",
                ),
            ],
            edges=[
                KnowledgeEdge(
                    id="edge:1",
                    source_id="router:1",
                    target_id="missing:1",
                    type=RelationshipType.DEPENDS_ON,
                ),
            ],
        )


def test_graph_snapshot_from_dict() -> None:
    graph = GraphSnapshot.from_dict({
        "nodes": [
            {
                "id": "site:1",
                "type": "site",
                "label": "Site 1",
            },
            {
                "id": "router:1",
                "type": "router",
                "label": "Router 1",
            },
        ],
        "edges": [
            {
                "id": "edge:1",
                "source": "site:1",
                "target": "router:1",
                "type": "contains",
            },
        ],
    })

    result = graph.to_dict()

    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert result["edges"][0]["type"] == "contains"


def test_impact_path_validation() -> None:
    path = ImpactPath(
        source_id="site:1",
        target_id="customer:1",
        node_ids=[
            "site:1",
            "router:1",
            "customer:1",
        ],
        edge_ids=[
            "edge:1",
            "edge:2",
        ],
        confidence=0.91,
    )

    assert path.node_ids[0] == "site:1"
    assert path.node_ids[-1] == "customer:1"
    assert path.confidence == 0.91


def test_impact_path_rejects_broken_edge_count() -> None:
    with pytest.raises(
        ValueError,
        match="edge count",
    ):
        ImpactPath(
            source_id="site:1",
            target_id="router:1",
            node_ids=[
                "site:1",
                "switch:1",
                "router:1",
            ],
            edge_ids=[
                "edge:1",
            ],
        )


def test_normalize_graph_returns_snapshot() -> None:
    graph = normalize_graph({
        "nodes": [
            {
                "id": "site:1",
                "type": "site",
                "label": "Site",
            },
        ],
        "edges": [],
    })

    assert isinstance(
        graph,
        GraphSnapshot,
    )
    assert graph.node_count == 1


def test_normalize_graph_none_returns_empty_graph() -> None:
    graph = normalize_graph(None)

    assert graph.node_count == 0
    assert graph.edge_count == 0
