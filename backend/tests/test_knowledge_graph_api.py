from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import knowledge_graph
from app.api.v1.router import api_router


def run(coroutine):
    return asyncio.run(coroutine)


async def fake_dashboard(
    refresh: bool = False,
) -> dict:
    return {
        "devices": [
            {
                "name": "Core Router",
                "ip_address": "10.0.0.1",
                "device_type":
                    "MikroTik RouterOS",
                "site": "Riyadh",
                "status": "online",
                "source": "influxdb",
                "metrics": {
                    "metrics": {
                        "cpu_usage": 20,
                        "memory_usage": 30,
                        "uptime_seconds": 1000,
                        "latency_ms": 2.5,
                        "packet_loss": 0,
                    },
                    "is_live": True,
                },
            },
            {
                "name": "Branch Router",
                "ip_address": "10.0.0.2",
                "device_type":
                    "MikroTik RouterOS",
                "site": "Jeddah",
                "status": "offline",
                "source": "influxdb",
                "metrics": {
                    "metrics": {},
                    "is_live": False,
                },
            },
        ],
        "cached": not refresh,
        "generated_at_unix": 1234.5,
    }


@pytest.fixture(autouse=True)
def mock_dashboard(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        knowledge_graph,
        "get_dashboard_snapshot",
        fake_dashboard,
    )


def test_router_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/knowledge-graph"
        in paths
    )


def test_build_runtime_graph() -> None:
    graph = run(
        knowledge_graph.build_runtime_graph()
    )

    assert graph.node_count == 4
    assert graph.edge_count == 4
    assert (
        graph.metadata["source"]
        == "dashboard"
    )


def test_get_full_graph() -> None:
    result = run(
        knowledge_graph.knowledge_graph()
    )

    assert result["node_count"] == 4
    assert result["edge_count"] == 4


def test_summary_endpoint() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_summary()
    )

    assert result["node_count"] == 4
    assert result["edge_count"] == 4
    assert result["component_count"] == 2


def test_nodes_filter_by_type() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_nodes(
            node_type="router"
        )
    )

    assert result["count"] == 2


def test_get_node() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_node(
            "device:10.0.0.1"
        )
    )

    assert result["label"] == "Core Router"
    assert result["status"] == "online"


def test_missing_node_returns_404() -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            knowledge_graph
            .knowledge_graph_node(
                "device:missing"
            )
        )

    assert exc.value.status_code == 404


def test_neighbors_endpoint() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_neighbors(
            "device:10.0.0.1"
        )
    )

    assert result["count"] == 1
    assert (
        result["nodes"][0]["type"]
        == "site"
    )


def test_path_not_found() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_path(
            source_id="device:10.0.0.1",
            target_id="device:10.0.0.2",
        )
    )

    assert result == {
        "found": False,
        "path": None,
    }


def test_invalid_relationship_returns_400() -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        knowledge_graph._relationship_filter(
            "invalid-relation"
        )

    assert exc.value.status_code == 400


def test_decision_timeline_endpoint() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_decision_timeline(
            "device:10.0.0.1",
            max_depth=10,
        )
    )

    assert (
        result["source_node_id"]
        == "device:10.0.0.1"
    )

    assert (
        result["statistics"]
        ["event_count"]
        == 7
    )

    assert result["events"][0]["type"] == (
        "observation"
    )

    assert result["events"][-1]["type"] == (
        "decision"
    )

    assert result["final_event"] is not None

    assert (
        result["final_event"]["actionable"]
        is True
    )


def test_decision_timeline_missing_node_returns_404() -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            knowledge_graph
            .knowledge_graph_decision_timeline(
                "device:missing",
                max_depth=10,
            )
        )

    assert exc.value.status_code == 404

    assert (
        "Graph node not found"
        in str(exc.value.detail)
    )


def test_decision_timeline_route_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/knowledge-graph/"
        "nodes/{node_id}/decision/timeline"
        in paths
    )


def test_execution_plan_endpoint() -> None:
    result = run(
        knowledge_graph
        .knowledge_graph_execution_plan(
            "device:10.0.0.1",
            max_depth=10,
        )
    )

    assert (
        result["source_node_id"]
        == "device:10.0.0.1"
    )

    assert result["dry_run_only"] is True

    assert (
        result["automatic_execution_allowed"]
        is False
    )

    assert (
        result["statistics"]["step_count"]
        == 7
    )

    assert (
        result["statistics"]
        ["mutating_step_count"]
        == 1
    )

    assert (
        result["statistics"]
        ["rollback_available"]
        is True
    )

    command_step = next(
        step
        for step in result["steps"]
        if step["type"] == "command"
    )

    assert command_step["command"].startswith(
        "DRY_RUN_ONLY:"
    )

    assert (
        command_step["requires_approval"]
        is True
    )


def test_execution_plan_missing_node_returns_404() -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            knowledge_graph
            .knowledge_graph_execution_plan(
                "device:missing",
                max_depth=10,
            )
        )

    assert exc.value.status_code == 404

    assert (
        "Graph node not found"
        in str(exc.value.detail)
    )


def test_execution_plan_route_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/knowledge-graph/"
        "nodes/{node_id}/decision/execution-plan"
        in paths
    )
