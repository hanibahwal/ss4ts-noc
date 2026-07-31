from __future__ import annotations

from app.models.device import (
    DeviceSnapshot,
    DeviceStatus,
)
from app.models.interface import (
    InterfaceKind,
    InterfaceSnapshot,
    InterfaceStatus,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    NodeType,
    RelationshipType,
)
from app.services.knowledge_graph import (
    KnowledgeGraphBuilder,
    build_graph_from_devices,
    merge_graph_snapshots,
)


def make_device(
    *,
    router_ip: str = "10.0.0.1",
    identity: str = "Core Router",
    site: str | None = "Riyadh",
    metadata: dict | None = None,
) -> DeviceSnapshot:
    return DeviceSnapshot(
        router_ip=router_ip,
        identity=identity,
        status=DeviceStatus.ONLINE,
        site=site,
        interfaces=[
            InterfaceSnapshot(
                name="ether1",
                index=1,
                kind=InterfaceKind.ETHERNET,
                admin_status=InterfaceStatus.UP,
                oper_status=InterfaceStatus.UP,
                speed_bps=1_000_000_000,
                rx_bps=100_000_000,
                tx_bps=50_000_000,
            ),
            InterfaceSnapshot(
                name="ether2",
                index=2,
                kind=InterfaceKind.ETHERNET,
                admin_status=InterfaceStatus.UP,
                oper_status=InterfaceStatus.DOWN,
                rx_errors=10,
            ),
        ],
        metadata=dict(metadata or {}),
    )


def test_build_graph_from_one_device() -> None:
    graph = build_graph_from_devices([
        make_device(),
    ])

    assert graph.node_count == 4
    assert graph.edge_count == 4

    assert graph.metadata["site_count"] == 1
    assert graph.metadata["device_count"] == 1
    assert graph.metadata["interface_count"] == 2


def test_graph_contains_expected_node_types() -> None:
    graph = build_graph_from_devices([
        make_device(),
    ])

    types = {
        node.type
        for node in graph.nodes
    }

    assert NodeType.SITE in types
    assert NodeType.ROUTER in types
    assert NodeType.INTERFACE in types


def test_device_without_site_builds_successfully() -> None:
    graph = build_graph_from_devices([
        make_device(site=None),
    ])

    assert graph.node_count == 3
    assert graph.edge_count == 2
    assert graph.metadata["site_count"] == 0


def test_builder_accepts_raw_device_dictionary() -> None:
    graph = build_graph_from_devices([
        {
            "router_ip": "192.168.1.1",
            "identity": "Branch Router",
            "status": "online",
            "site": "Jeddah",
            "interfaces": [
                {
                    "name": "ether1",
                    "index": 1,
                    "admin_status": "up",
                    "oper_status": "up",
                },
            ],
        },
    ])

    assert graph.metadata["device_count"] == 1
    assert graph.metadata["interface_count"] == 1


def test_interface_metadata_is_preserved() -> None:
    graph = build_graph_from_devices([
        make_device(),
    ])

    interface = next(
        node
        for node in graph.nodes
        if (
            node.type == NodeType.INTERFACE
            and node.label == "ether2"
        )
    )

    assert interface.status == "down"
    assert interface.metadata["total_errors"] == 10
    assert (
        "admin_up_oper_down"
        in interface.metadata["health_flags"]
    )


def test_metadata_connected_to_relationship() -> None:
    first = make_device(
        router_ip="10.0.0.1",
        identity="Router A",
        metadata={
            "connected_to": [
                "10.0.0.2",
            ],
        },
    )

    second = make_device(
        router_ip="10.0.0.2",
        identity="Router B",
    )

    graph = build_graph_from_devices([
        first,
        second,
    ])

    relationship = next(
        edge
        for edge in graph.edges
        if edge.type
        == RelationshipType.CONNECTED_TO
    )

    assert relationship.bidirectional is True
    assert relationship.source_id == "device:10.0.0.1"
    assert relationship.target_id == "device:10.0.0.2"


def test_unknown_relationship_target_is_ignored() -> None:
    graph = build_graph_from_devices([
        make_device(
            metadata={
                "depends_on": [
                    "192.0.2.99",
                ],
            },
        ),
    ])

    assert not any(
        edge.type
        == RelationshipType.DEPENDS_ON
        for edge in graph.edges
    )


def test_duplicate_devices_are_deduplicated() -> None:
    builder = KnowledgeGraphBuilder()

    graph = builder.build_from_devices([
        make_device(identity="Old Name"),
        make_device(identity="New Name"),
    ])

    routers = [
        node
        for node in graph.nodes
        if node.type == NodeType.ROUTER
    ]

    assert len(routers) == 1
    assert routers[0].label == "New Name"


def test_ids_are_deterministic() -> None:
    device = make_device()

    builder = KnowledgeGraphBuilder()

    first = builder.build_from_devices([
        device,
    ])

    second = builder.build_from_devices([
        device,
    ])

    assert {
        node.id
        for node in first.nodes
    } == {
        node.id
        for node in second.nodes
    }

    assert {
        edge.id
        for edge in first.edges
    } == {
        edge.id
        for edge in second.edges
    }


def test_merge_graph_snapshots() -> None:
    first = build_graph_from_devices([
        make_device(
            router_ip="10.0.0.1",
            identity="Router A",
        ),
    ])

    second = build_graph_from_devices([
        make_device(
            router_ip="10.0.0.2",
            identity="Router B",
            site="Jeddah",
        ),
    ])

    merged = merge_graph_snapshots(
        first,
        second,
    )

    assert isinstance(
        merged,
        GraphSnapshot,
    )

    assert merged.metadata[
        "merged_snapshot_count"
    ] == 2

    assert len([
        node
        for node in merged.nodes
        if node.type == NodeType.ROUTER
    ]) == 2
