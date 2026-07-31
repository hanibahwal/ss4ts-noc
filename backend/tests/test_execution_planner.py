from __future__ import annotations

import pytest

from app.models.execution_plan import (
    ExecutionPlan,
    ExecutionPlanStatus,
    ExecutionStepType,
)
from app.models.knowledge_graph import (
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from app.services.execution_planner import (
    ExecutionPlanBuilder,
    build_execution_plan,
)


def make_graph(
    *,
    source_active: bool = False,
    with_backup: bool = False,
    power_alarm: bool = False,
    upstream_failed: bool = False,
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


def test_builder_returns_execution_plan() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    assert isinstance(
        plan,
        ExecutionPlan,
    )

    assert plan.step_count == 7

    assert (
        plan.status
        == ExecutionPlanStatus.PENDING_APPROVAL
    )


def test_plan_is_dry_run_only() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    assert plan.dry_run_only is True

    assert (
        plan.automatic_execution_allowed
        is False
    )

    assert (
        plan.metadata["execution_enabled"]
        is False
    )


def test_plan_step_order() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    assert [
        step.step_type
        for step in plan.steps
    ] == [
        ExecutionStepType.OBSERVE,
        ExecutionStepType.VALIDATE,
        ExecutionStepType.VALIDATE,
        ExecutionStepType.APPROVAL,
        ExecutionStepType.COMMAND,
        ExecutionStepType.VERIFY,
        ExecutionStepType.NOTIFY,
    ]


def test_command_is_dry_run_and_reversible() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    command_step = next(
        step
        for step in plan.steps
        if (
            step.step_type
            == ExecutionStepType.COMMAND
        )
    )

    assert command_step.command is not None

    assert command_step.command.startswith(
        "DRY_RUN_ONLY:"
    )

    assert (
        command_step.rollback_command
        is not None
    )

    assert (
        command_step.rollback_command
        .startswith("DRY_RUN_ONLY:")
    )

    assert command_step.requires_approval is True

    assert command_step.automatic_allowed is False


def test_power_cause_creates_power_validation() -> None:
    plan = build_execution_plan(
        make_graph(
            power_alarm=True
        ),
        "device:core",
    )

    validation = plan.steps[1]

    assert "power" in (
        validation.title.lower()
    )

    assert (
        plan.metadata["primary_cause_id"]
        .startswith("cause:power:")
    )


def test_upstream_cause_creates_upstream_validation() -> None:
    plan = build_execution_plan(
        make_graph(
            upstream_failed=True
        ),
        "device:core",
    )

    validation = plan.steps[1]

    assert "upstream" in (
        validation.title.lower()
    )

    assert (
        plan.metadata["primary_cause_id"]
        .startswith("cause:upstream:")
    )


def test_plan_contains_dependency_chain() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    for index, step in enumerate(
        plan.steps[1:],
        start=1,
    ):
        previous = plan.steps[
            index - 1
        ]

        assert previous.step_id in (
            step.depends_on
        )


def test_plan_has_rollback_available() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    assert plan.rollback_available is True
    assert plan.mutating_step_count == 1


def test_plan_serializes() -> None:
    plan = build_execution_plan(
        make_graph(),
        "device:core",
    )

    payload = plan.to_dict()

    assert payload["statistics"]["step_count"] == 7

    assert (
        payload["statistics"]
        ["mutating_step_count"]
        == 1
    )

    assert (
        payload["statistics"]
        ["rollback_available"]
        is True
    )


def test_invalid_depth_rejected() -> None:
    builder = ExecutionPlanBuilder(
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
    builder = ExecutionPlanBuilder(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        builder.build(
            "device:missing"
        )
