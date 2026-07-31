from __future__ import annotations

import pytest

from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.knowledge_graph_query import (
    KnowledgeGraphQuery,
)


def make_graph() -> GraphSnapshot:
    nodes = [
        KnowledgeNode(
            id="core",
            type=NodeType.ROUTER,
            label="Core",
        ),
        KnowledgeNode(
            id="distribution",
            type=NodeType.SWITCH,
            label="Distribution",
        ),
        KnowledgeNode(
            id="access-a",
            type=NodeType.SWITCH,
            label="Access A",
        ),
        KnowledgeNode(
            id="access-b",
            type=NodeType.SWITCH,
            label="Access B",
        ),
        KnowledgeNode(
            id="customer",
            type=NodeType.CUSTOMER_SERVICE,
            label="Customer",
        ),
        KnowledgeNode(
            id="isolated",
            type=NodeType.DEVICE,
            label="Isolated",
        ),
    ]

    edges = [
        KnowledgeEdge(
            id="distribution-core",
            source_id="distribution",
            target_id="core",
            type=RelationshipType.DEPENDS_ON,
        ),
        KnowledgeEdge(
            id="access-a-distribution",
            source_id="access-a",
            target_id="distribution",
            type=RelationshipType.DEPENDS_ON,
        ),
        KnowledgeEdge(
            id="access-b-distribution",
            source_id="access-b",
            target_id="distribution",
            type=RelationshipType.DEPENDS_ON,
        ),
        KnowledgeEdge(
            id="customer-access-a",
            source_id="customer",
            target_id="access-a",
            type=RelationshipType.DEPENDS_ON,
        ),
        KnowledgeEdge(
            id="access-a-access-b",
            source_id="access-a",
            target_id="access-b",
            type=RelationshipType.CONNECTED_TO,
            bidirectional=True,
        ),
    ]

    return GraphSnapshot(
        nodes=nodes,
        edges=edges,
    )


def test_node_lookup() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    assert query.node("core").label == "Core"


def test_unknown_node_raises_key_error() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        query.node("missing")


def test_neighbors_support_relationship_filter() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    neighbors = query.neighbors(
        "access-a",
        relationships={
            RelationshipType.CONNECTED_TO,
        },
    )

    assert {
        node.id
        for node in neighbors
    } == {
        "access-b",
    }


def test_direct_dependencies() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    dependencies = query.dependencies(
        "access-a"
    )

    assert [
        node.id
        for node in dependencies
    ] == [
        "distribution",
    ]


def test_recursive_dependencies() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    dependencies = query.dependencies(
        "customer",
        recursive=True,
    )

    assert {
        node.id
        for node in dependencies
    } == {
        "access-a",
        "distribution",
        "core",
    }


def test_recursive_dependents() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    dependents = query.dependents(
        "core",
        recursive=True,
    )

    assert {
        node.id
        for node in dependents
    } == {
        "distribution",
        "access-a",
        "access-b",
        "customer",
    }


def test_shortest_path() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    path = query.shortest_path(
        "customer",
        "core",
        direction="outgoing",
        relationships={
            RelationshipType.DEPENDS_ON,
        },
    )

    assert path is not None

    assert path.node_ids == [
        "customer",
        "access-a",
        "distribution",
        "core",
    ]

    assert len(path.edge_ids) == 3


def test_shortest_path_returns_none() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    path = query.shortest_path(
        "isolated",
        "core",
    )

    assert path is None


def test_all_paths_respects_relationship_filter() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    paths = query.all_paths(
        "customer",
        "core",
        direction="outgoing",
        relationships={
            RelationshipType.DEPENDS_ON,
        },
    )

    assert len(paths) == 1
    assert paths[0].target_id == "core"


def test_blast_radius() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    affected = query.blast_radius(
        "core"
    )

    assert {
        node.id
        for node in affected
    } == {
        "distribution",
        "access-a",
        "access-b",
        "customer",
    }


def test_impact_paths() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    paths = query.impact_paths(
        "core"
    )

    targets = {
        path.target_id
        for path in paths
    }

    assert {
        "distribution",
        "access-a",
        "access-b",
        "customer",
    }.issubset(targets)


def test_connected_components() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    components = (
        query.connected_components()
    )

    sizes = sorted(
        (
            len(component)
            for component in components
        ),
        reverse=True,
    )

    assert sizes == [
        5,
        1,
    ]


def test_traversal_handles_cycles() -> None:
    graph = make_graph()

    graph = GraphSnapshot(
        nodes=graph.nodes,
        edges=[
            *graph.edges,
            KnowledgeEdge(
                id="core-customer",
                source_id="core",
                target_id="customer",
                type=RelationshipType.DEPENDS_ON,
            ),
        ],
    )

    query = KnowledgeGraphQuery(
        graph
    )

    result = query.traverse(
        "customer",
        direction="outgoing",
        relationships={
            RelationshipType.DEPENDS_ON,
        },
        max_depth=20,
    )

    assert len({
        node.id
        for node in result
    }) == len(result)


def test_max_depth_limits_traversal() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    result = query.dependencies(
        "customer",
        recursive=True,
        max_depth=1,
    )

    assert [
        node.id
        for node in result
    ] == [
        "access-a",
    ]


def test_invalid_direction_rejected() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        query.neighbors(
            "core",
            direction="sideways",
        )


def test_bidirectional_neighbor_from_reverse_endpoint() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    neighbors = query.neighbors(
        "access-b",
        relationships={
            RelationshipType.CONNECTED_TO,
        },
    )

    assert {
        node.id
        for node in neighbors
    } == {
        "access-a",
    }


def test_bidirectional_neighbor_never_returns_self() -> None:
    query = KnowledgeGraphQuery(
        make_graph()
    )

    for node_id in (
        "access-a",
        "access-b",
    ):
        neighbors = query.neighbors(
            node_id,
            relationships={
                RelationshipType.CONNECTED_TO,
            },
        )

        assert node_id not in {
            node.id
            for node in neighbors
        }
