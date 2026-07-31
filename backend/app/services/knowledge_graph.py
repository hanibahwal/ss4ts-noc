from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
import re
from typing import Any

from app.models.device import (
    DeviceSnapshot,
)
from app.models.interface import (
    InterfaceSnapshot,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _slug(
    value: Any,
    default: str = "unknown",
) -> str:
    text = _text(
        value,
        default,
    ).lower()

    normalized = re.sub(
        r"[^a-z0-9._:-]+",
        "-",
        text,
    )

    normalized = re.sub(
        r"-+",
        "-",
        normalized,
    ).strip("-")

    return normalized or default


def _metadata_list(
    metadata: dict[str, Any],
    key: str,
) -> list[str]:
    value = metadata.get(key)

    if value is None:
        return []

    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        candidates = list(value)
    else:
        return []

    result: list[str] = []

    for item in candidates:
        normalized = _text(item)

        if (
            normalized
            and normalized not in result
        ):
            result.append(normalized)

    return result


class KnowledgeGraphBuilder:
    """
    Build a deterministic SS4TS Knowledge Graph from device inventory.

    The builder converts canonical DeviceSnapshot and InterfaceSnapshot
    models into graph nodes and relationships. It does not perform
    network I/O and can therefore be used by APIs, jobs and tests.
    """

    def __init__(self) -> None:
        self._nodes: dict[
            str,
            KnowledgeNode,
        ] = {}

        self._edges: dict[
            str,
            KnowledgeEdge,
        ] = {}

        self._device_aliases: dict[
            str,
            str,
        ] = {}

        self._pending_relationships: list[
            tuple[
                str,
                str,
                RelationshipType,
            ]
        ] = []

    def reset(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._device_aliases.clear()
        self._pending_relationships.clear()

    @staticmethod
    def site_node_id(
        site: str,
    ) -> str:
        return f"site:{_slug(site)}"

    @staticmethod
    def device_node_id(
        device: DeviceSnapshot,
    ) -> str:
        identity = (
            device.router_ip
            or device.serial_number
            or device.identity
        )

        return f"device:{_slug(identity)}"

    @staticmethod
    def interface_node_id(
        device: DeviceSnapshot,
        interface: InterfaceSnapshot,
    ) -> str:
        device_key = _slug(
            device.router_ip
            or device.identity
        )

        interface_key = (
            str(interface.index)
            if interface.index is not None
            else _slug(interface.name)
        )

        return (
            f"interface:{device_key}:"
            f"{interface_key}"
        )

    @staticmethod
    def edge_id(
        source_id: str,
        relationship: RelationshipType,
        target_id: str,
    ) -> str:
        return (
            f"edge:{_slug(source_id)}:"
            f"{relationship.value}:"
            f"{_slug(target_id)}"
        )

    def add_node(
        self,
        node: KnowledgeNode,
    ) -> KnowledgeNode:
        self._nodes[node.id] = node

        return node

    def add_edge(
        self,
        edge: KnowledgeEdge,
    ) -> KnowledgeEdge:
        if edge.source_id not in self._nodes:
            raise ValueError(
                "Cannot add edge with unknown "
                f"source node: {edge.source_id}"
            )

        if edge.target_id not in self._nodes:
            raise ValueError(
                "Cannot add edge with unknown "
                f"target node: {edge.target_id}"
            )

        self._edges[edge.id] = edge

        return edge

    def add_site(
        self,
        site: str,
        *,
        location: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        normalized_site = _text(site)

        if not normalized_site:
            raise ValueError(
                "Site name must not be empty"
            )

        node_id = self.site_node_id(
            normalized_site
        )

        existing = self._nodes.get(node_id)

        if existing is not None:
            if (
                location
                and not existing.location
            ):
                existing.location = _text(
                    location
                )

            if metadata:
                existing.metadata.update(
                    metadata
                )

            return existing

        return self.add_node(
            KnowledgeNode(
                id=node_id,
                type=NodeType.SITE,
                label=normalized_site,
                location=_text(
                    location
                ) or None,
                metadata=dict(
                    metadata or {}
                ),
            )
        )

    def add_interface(
        self,
        device: DeviceSnapshot,
        interface: InterfaceSnapshot,
        *,
        device_node_id: str | None = None,
    ) -> KnowledgeNode:
        parent_id = (
            device_node_id
            or self.device_node_id(device)
        )

        if parent_id not in self._nodes:
            raise ValueError(
                "Device node must exist before "
                "adding its interfaces"
            )

        node_id = self.interface_node_id(
            device,
            interface,
        )

        node = self.add_node(
            KnowledgeNode(
                id=node_id,
                type=NodeType.INTERFACE,
                label=interface.name,
                status=interface.state,
                active=interface.is_admin_up,
                confidence=1.0,
                metadata={
                    "device_node_id":
                        parent_id,
                    "router_ip":
                        device.router_ip,
                    "if_index":
                        interface.index,
                    "kind":
                        interface.kind.value,
                    "admin_status":
                        interface.admin_status.value,
                    "oper_status":
                        interface.oper_status.value,
                    "speed_bps":
                        interface.speed_bps,
                    "rx_bps":
                        interface.rx_bps,
                    "tx_bps":
                        interface.tx_bps,
                    "total_errors":
                        interface.total_errors,
                    "total_drops":
                        interface.total_drops,
                    "utilization_percent":
                        interface.utilization_percent,
                    "health_flags":
                        interface.health_flags,
                    "mac_address":
                        interface.mac_address,
                    "description":
                        interface.description,
                    "alias":
                        interface.alias,
                },
            )
        )

        edge = KnowledgeEdge(
            id=self.edge_id(
                parent_id,
                RelationshipType.CONTAINS,
                node.id,
            ),
            source_id=parent_id,
            target_id=node.id,
            type=RelationshipType.CONTAINS,
            label="contains interface",
        )

        self.add_edge(edge)

        return node

    def add_device(
        self,
        device: DeviceSnapshot | dict[str, Any],
    ) -> KnowledgeNode:
        snapshot = (
            device
            if isinstance(
                device,
                DeviceSnapshot,
            )
            else DeviceSnapshot.from_dict(
                device
            )
        )

        node_id = self.device_node_id(
            snapshot
        )

        device_node = self.add_node(
            KnowledgeNode(
                id=node_id,
                type=NodeType.ROUTER,
                label=snapshot.identity,
                status=snapshot.status.value,
                external_id=(
                    snapshot.serial_number
                    or snapshot.router_ip
                    or None
                ),
                site=snapshot.site,
                location=snapshot.location,
                active=snapshot.is_online,
                confidence=1.0,
                metadata={
                    "router_ip":
                        snapshot.router_ip,
                    "platform":
                        snapshot.platform.value,
                    "board_name":
                        snapshot.board_name,
                    "model":
                        snapshot.model,
                    "architecture":
                        snapshot.architecture,
                    "serial_number":
                        snapshot.serial_number,
                    "routeros_version":
                        snapshot.routeros_version,
                    "firmware_version":
                        snapshot.firmware_version,
                    "uptime":
                        snapshot.uptime,
                    "uptime_seconds":
                        snapshot.uptime_seconds,
                    "cpu_usage":
                        snapshot.cpu_usage,
                    "memory_usage":
                        snapshot.memory_usage,
                    "storage_usage":
                        snapshot.storage_usage,
                    "temperature_celsius":
                        snapshot.temperature_celsius,
                    "interface_count":
                        snapshot.interface_count,
                    "health_flags":
                        snapshot.health_flags,
                    "summary":
                        snapshot.summary,
                    **dict(snapshot.metadata),
                },
            )
        )

        aliases = {
            snapshot.router_ip,
            snapshot.identity,
            snapshot.serial_number,
            node_id,
        }

        for alias in aliases:
            normalized = _text(alias)

            if normalized:
                self._device_aliases[
                    normalized.lower()
                ] = node_id

        if snapshot.site:
            site_node = self.add_site(
                snapshot.site,
                location=snapshot.location,
            )

            self.add_edge(
                KnowledgeEdge(
                    id=self.edge_id(
                        site_node.id,
                        RelationshipType.CONTAINS,
                        device_node.id,
                    ),
                    source_id=site_node.id,
                    target_id=device_node.id,
                    type=RelationshipType.CONTAINS,
                    label="contains device",
                )
            )

            self.add_edge(
                KnowledgeEdge(
                    id=self.edge_id(
                        device_node.id,
                        RelationshipType.LOCATED_AT,
                        site_node.id,
                    ),
                    source_id=device_node.id,
                    target_id=site_node.id,
                    type=RelationshipType.LOCATED_AT,
                    label="located at site",
                )
            )

        for interface in snapshot.interfaces:
            self.add_interface(
                snapshot,
                interface,
                device_node_id=device_node.id,
            )

        relationship_keys = {
            "connected_to":
                RelationshipType.CONNECTED_TO,
            "depends_on":
                RelationshipType.DEPENDS_ON,
            "backed_up_by":
                RelationshipType.BACKED_UP_BY,
        }

        for (
            metadata_key,
            relationship_type,
        ) in relationship_keys.items():
            for target_alias in _metadata_list(
                snapshot.metadata,
                metadata_key,
            ):
                self._pending_relationships.append(
                    (
                        device_node.id,
                        target_alias,
                        relationship_type,
                    )
                )

        return device_node

    def _resolve_pending_relationships(
        self,
    ) -> None:
        for (
            source_id,
            target_alias,
            relationship_type,
        ) in self._pending_relationships:
            target_id = self._device_aliases.get(
                target_alias.lower()
            )

            if (
                target_id is None
                or target_id == source_id
            ):
                continue

            edge = KnowledgeEdge(
                id=self.edge_id(
                    source_id,
                    relationship_type,
                    target_id,
                ),
                source_id=source_id,
                target_id=target_id,
                type=relationship_type,
                label=relationship_type.value,
                bidirectional=(
                    relationship_type
                    == RelationshipType.CONNECTED_TO
                ),
            )

            self.add_edge(edge)

        self._pending_relationships.clear()

    def snapshot(
        self,
        *,
        generated_at: str | None = None,
        version: str = "1.0",
        metadata: dict[str, Any] | None = None,
    ) -> GraphSnapshot:
        self._resolve_pending_relationships()

        return GraphSnapshot(
            nodes=list(
                self._nodes.values()
            ),
            edges=list(
                self._edges.values()
            ),
            generated_at=generated_at,
            version=version,
            metadata={
                "builder":
                    "KnowledgeGraphBuilder",
                "device_count":
                    sum(
                        1
                        for node
                        in self._nodes.values()
                        if node.type
                        == NodeType.ROUTER
                    ),
                "site_count":
                    sum(
                        1
                        for node
                        in self._nodes.values()
                        if node.type
                        == NodeType.SITE
                    ),
                "interface_count":
                    sum(
                        1
                        for node
                        in self._nodes.values()
                        if node.type
                        == NodeType.INTERFACE
                    ),
                **dict(metadata or {}),
            },
        )

    def build_from_devices(
        self,
        devices: Iterable[
            DeviceSnapshot | dict[str, Any]
        ],
        *,
        reset: bool = True,
        generated_at: str | None = None,
        version: str = "1.0",
        metadata: dict[str, Any] | None = None,
    ) -> GraphSnapshot:
        if reset:
            self.reset()

        for device in devices:
            if isinstance(
                device,
                (
                    DeviceSnapshot,
                    dict,
                ),
            ):
                self.add_device(device)

        return self.snapshot(
            generated_at=generated_at,
            version=version,
            metadata=metadata,
        )


def build_graph_from_devices(
    devices: Iterable[
        DeviceSnapshot | dict[str, Any]
    ],
    *,
    generated_at: str | None = None,
    version: str = "1.0",
    metadata: dict[str, Any] | None = None,
) -> GraphSnapshot:
    """
    Functional entry point for building one graph snapshot.
    """

    return KnowledgeGraphBuilder().build_from_devices(
        devices,
        generated_at=generated_at,
        version=version,
        metadata=metadata,
    )


def merge_graph_snapshots(
    *snapshots: GraphSnapshot,
    generated_at: str | None = None,
    version: str = "1.0",
    metadata: dict[str, Any] | None = None,
) -> GraphSnapshot:
    """
    Merge graph snapshots by deterministic node and edge identifiers.

    Values from later snapshots replace values from earlier snapshots.
    """

    nodes: dict[
        str,
        KnowledgeNode,
    ] = {}

    edges: dict[
        str,
        KnowledgeEdge,
    ] = {}

    for snapshot in snapshots:
        if not isinstance(
            snapshot,
            GraphSnapshot,
        ):
            raise TypeError(
                "merge_graph_snapshots accepts "
                "GraphSnapshot instances only"
            )

        for node in snapshot.nodes:
            nodes[node.id] = replace(
                node,
                metadata=dict(node.metadata),
            )

        for edge in snapshot.edges:
            edges[edge.id] = replace(
                edge,
                metadata=dict(edge.metadata),
            )

    return GraphSnapshot(
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        generated_at=generated_at,
        version=version,
        metadata={
            "merged_snapshot_count":
                len(snapshots),
            **dict(metadata or {}),
        },
    )
