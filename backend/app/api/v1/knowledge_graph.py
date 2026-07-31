from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.dashboard import (
    dashboard as get_dashboard_snapshot,
)
from app.models.device import DeviceSnapshot
from app.models.knowledge_graph import (
    GraphSnapshot,
    RelationshipType,
)
from app.services.knowledge_graph import (
    build_graph_from_devices,
)
from app.services.knowledge_graph_query import (
    KnowledgeGraphQuery,
)


Direction = Literal[
    "outgoing",
    "incoming",
    "both",
]


router = APIRouter(
    prefix="/knowledge-graph",
    tags=["knowledge-graph"],
)


def _relationship_filter(
    value: str | None,
) -> set[RelationshipType] | None:
    if value is None:
        return None

    relationships: set[RelationshipType] = set()

    for item in value.split(","):
        normalized = item.strip().lower()

        if not normalized:
            continue

        try:
            relationships.add(
                RelationshipType(normalized)
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unknown relationship type: "
                    f"{normalized}"
                ),
            ) from exc

    return relationships or None


def _device_payload(
    device: dict,
) -> dict:
    metrics_wrapper = device.get("metrics")

    if not isinstance(metrics_wrapper, dict):
        metrics_wrapper = {}

    metrics = metrics_wrapper.get("metrics")

    if not isinstance(metrics, dict):
        metrics = {}

    metadata = {
        "source": device.get("source"),
        "availability":
            metrics_wrapper.get("availability"),
        "is_live":
            metrics_wrapper.get("is_live"),
        "latency_ms":
            metrics.get("latency_ms"),
        "packet_loss":
            metrics.get("packet_loss"),
    }

    return {
        **device,
        "router_ip": (
            device.get("router_ip")
            or device.get("ip_address")
            or device.get("ip")
        ),
        "identity": (
            device.get("identity")
            or device.get("name")
            or device.get("device_name")
        ),
        "platform": (
            device.get("platform")
            or device.get("device_type")
        ),
        "cpu_usage":
            metrics.get("cpu_usage"),
        "memory_usage":
            metrics.get("memory_usage"),
        "temperature":
            metrics.get("temperature"),
        "uptime_seconds":
            metrics.get("uptime_seconds"),
        "last_seen": (
            device.get("last_seen")
            or metrics_wrapper.get("last_seen")
        ),
        "metadata": metadata,
    }


async def build_runtime_graph(
    *,
    refresh: bool = False,
) -> GraphSnapshot:
    snapshot = await get_dashboard_snapshot(
        refresh=refresh
    )

    devices = snapshot.get("devices", [])

    if not isinstance(devices, list):
        devices = []

    normalized_devices: list[DeviceSnapshot] = []

    for item in devices:
        if not isinstance(item, dict):
            continue

        try:
            normalized_devices.append(
                DeviceSnapshot.from_dict(
                    _device_payload(item)
                )
            )
        except (TypeError, ValueError):
            continue

    return build_graph_from_devices(
        normalized_devices,
        metadata={
            "source": "dashboard",
            "dashboard_cached":
                snapshot.get("cached", False),
            "dashboard_generated_at_unix":
                snapshot.get(
                    "generated_at_unix"
                ),
        },
    )


def _query(
    graph: GraphSnapshot,
) -> KnowledgeGraphQuery:
    return KnowledgeGraphQuery(graph)


def _node_or_404(
    query: KnowledgeGraphQuery,
    node_id: str,
):
    try:
        return query.node(node_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Graph node not found: {node_id}",
        ) from exc


@router.get("")
async def knowledge_graph(
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    return graph.to_dict()


@router.get("/summary")
async def knowledge_graph_summary(
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    query = _query(graph)

    components = query.connected_components(
        include_inactive=True
    )

    return {
        "node_count": graph.node_count,
        "edge_count": graph.edge_count,
        "active_node_count":
            len(graph.active_nodes),
        "active_edge_count":
            len(graph.active_edges),
        "component_count":
            len(components),
        "largest_component_size":
            max(
                (
                    len(component)
                    for component in components
                ),
                default=0,
            ),
        "metadata": graph.metadata,
    }


@router.get("/nodes")
async def knowledge_graph_nodes(
    node_type: str | None = None,
    active: bool | None = None,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    nodes = graph.nodes

    if node_type is not None:
        normalized_type = (
            node_type.strip().lower()
        )

        nodes = [
            node
            for node in nodes
            if node.type.value
            == normalized_type
        ]

    if active is not None:
        nodes = [
            node
            for node in nodes
            if node.active is active
        ]

    return {
        "count": len(nodes),
        "nodes": [
            node.to_dict()
            for node in nodes
        ],
    }


@router.get("/path")
async def knowledge_graph_path(
    source_id: str,
    target_id: str,
    direction: Direction = "both",
    relationships: str | None = None,
    max_depth: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 20,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    query = _query(graph)

    try:
        path = query.shortest_path(
            source_id,
            target_id,
            direction=direction,
            relationships=
                _relationship_filter(
                    relationships
                ),
            max_depth=max_depth,
            include_inactive=True,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "found": path is not None,
        "path": (
            path.to_dict()
            if path is not None
            else None
        ),
    }


@router.get("/nodes/{node_id}")
async def knowledge_graph_node(
    node_id: str,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    node = _node_or_404(
        _query(graph),
        node_id,
    )

    return node.to_dict()


@router.get("/nodes/{node_id}/neighbors")
async def knowledge_graph_neighbors(
    node_id: str,
    direction: Direction = "both",
    relationships: str | None = None,
    include_inactive: bool = False,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    query = _query(graph)

    _node_or_404(query, node_id)

    nodes = query.neighbors(
        node_id,
        direction=direction,
        relationships=
            _relationship_filter(
                relationships
            ),
        include_inactive=
            include_inactive,
    )

    return {
        "node_id": node_id,
        "count": len(nodes),
        "nodes": [
            node.to_dict()
            for node in nodes
        ],
    }


@router.get("/nodes/{node_id}/dependencies")
async def knowledge_graph_dependencies(
    node_id: str,
    recursive: bool = False,
    max_depth: Annotated[
        int,
        Query(
            ge=0,
            le=100,
        ),
    ] = 10,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    query = _query(graph)

    _node_or_404(query, node_id)

    nodes = query.dependencies(
        node_id,
        recursive=recursive,
        max_depth=max_depth,
    )

    return {
        "node_id": node_id,
        "recursive": recursive,
        "count": len(nodes),
        "nodes": [
            node.to_dict()
            for node in nodes
        ],
    }


@router.get("/nodes/{node_id}/dependents")
async def knowledge_graph_dependents(
    node_id: str,
    recursive: bool = False,
    max_depth: Annotated[
        int,
        Query(
            ge=0,
            le=100,
        ),
    ] = 10,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    query = _query(graph)

    _node_or_404(query, node_id)

    nodes = query.dependents(
        node_id,
        recursive=recursive,
        max_depth=max_depth,
    )

    return {
        "node_id": node_id,
        "recursive": recursive,
        "count": len(nodes),
        "nodes": [
            node.to_dict()
            for node in nodes
        ],
    }


@router.get("/nodes/{node_id}/blast-radius")
async def knowledge_graph_blast_radius(
    node_id: str,
    max_depth: Annotated[
        int,
        Query(
            ge=0,
            le=100,
        ),
    ] = 10,
    include_paths: bool = True,
    refresh: bool = False,
) -> dict:
    graph = await build_runtime_graph(
        refresh=refresh
    )

    query = _query(graph)

    source = _node_or_404(
        query,
        node_id,
    )

    affected = query.blast_radius(
        node_id,
        max_depth=max_depth,
        include_inactive=True,
    )

    paths = (
        query.impact_paths(
            node_id,
            max_depth=max_depth,
        )
        if include_paths
        else []
    )

    return {
        "source": source.to_dict(),
        "affected_count":
            len(affected),
        "affected_nodes": [
            node.to_dict()
            for node in affected
        ],
        "impact_paths": [
            path.to_dict()
            for path in paths
        ],
    }
