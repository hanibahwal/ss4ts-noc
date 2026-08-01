from __future__ import annotations

import pytest

from app.models.decision_trace import (
    DecisionTrace,
    DecisionTraceStageType,
)
from app.services.decision_trace import (
    DecisionTraceBuilder,
    build_decision_trace,
)
from tests.test_decision_fusion import (
    make_graph,
)


EXPECTED_STAGE_TYPES = [
    DecisionTraceStageType.TELEMETRY,
    DecisionTraceStageType.GRAPH_CONTEXT,
    DecisionTraceStageType.ROOT_CAUSE,
    DecisionTraceStageType.IMPACT,
    DecisionTraceStageType.RESILIENCE,
    DecisionTraceStageType.DECISION_FUSION,
    DecisionTraceStageType.EXPLANATION,
    DecisionTraceStageType.EXECUTION_PLAN,
]


def test_builder_returns_trace() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    assert isinstance(
        trace,
        DecisionTrace,
    )

    assert trace.stage_count == 8

    assert [
        stage.stage_type
        for stage in trace.stages
    ] == EXPECTED_STAGE_TYPES


def test_trace_is_read_only() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    assert trace.read_only is True
    assert trace.network_io_performed is False
    assert trace.device_command_executed is False


def test_power_cause_is_selected() -> None:
    trace = build_decision_trace(
        make_graph(
            power_alarm=True
        ),
        "device:core",
    )

    root_stage = next(
        stage
        for stage in trace.stages
        if (
            stage.stage_type
            == DecisionTraceStageType.ROOT_CAUSE
        )
    )

    assert root_stage.selected is True

    assert (
        root_stage.metadata
        ["primary_cause_id"]
        .startswith("cause:power:")
    )


def test_upstream_cause_is_selected() -> None:
    trace = build_decision_trace(
        make_graph(
            upstream_failed=True
        ),
        "device:core",
    )

    root_stage = next(
        stage
        for stage in trace.stages
        if (
            stage.stage_type
            == DecisionTraceStageType.ROOT_CAUSE
        )
    )

    assert (
        root_stage.metadata
        ["primary_cause_id"]
        .startswith("cause:upstream:")
    )


def test_impact_stage_contains_affected_nodes() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    impact = next(
        stage
        for stage in trace.stages
        if (
            stage.stage_type
            == DecisionTraceStageType.IMPACT
        )
    )

    assert (
        impact.metadata["affected_count"]
        == 3
    )

    assert set(
        impact.output_ids
    ) == {
        "device:distribution",
        "site:branch",
        "service:customer",
    }


def test_fusion_stage_is_selected() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    fusion = next(
        stage
        for stage in trace.stages
        if (
            stage.stage_type
            == (
                DecisionTraceStageType
                .DECISION_FUSION
            )
        )
    )

    assert fusion.selected is True
    assert fusion.output_ids == [
        trace.decision_id,
    ]


def test_explanation_stage_is_present() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    explanation = next(
        stage
        for stage in trace.stages
        if (
            stage.stage_type
            == DecisionTraceStageType.EXPLANATION
        )
    )

    assert (
        explanation.metadata
        ["explanation_item_count"]
        >= 1
    )


def test_execution_plan_is_dry_run() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    plan = next(
        stage
        for stage in trace.stages
        if (
            stage.stage_type
            == (
                DecisionTraceStageType
                .EXECUTION_PLAN
            )
        )
    )

    assert (
        plan.metadata["dry_run_only"]
        is True
    )

    assert (
        plan.metadata["execution_enabled"]
        is False
    )

    assert (
        plan.metadata["rollback_available"]
        is True
    )


def test_trace_serializes() -> None:
    trace = build_decision_trace(
        make_graph(),
        "device:core",
    )

    payload = trace.to_dict()

    assert payload["trace_id"]
    assert payload["decision_id"]
    assert (
        payload["statistics"]["stage_count"]
        == 8
    )

    assert (
        payload["safety"]
        ["device_command_executed"]
        is False
    )


def test_invalid_depth_rejected() -> None:
    builder = DecisionTraceBuilder(
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
    builder = DecisionTraceBuilder(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        builder.build(
            "device:missing"
        )


def test_invalid_result_type_rejected() -> None:
    builder = DecisionTraceBuilder(
        make_graph()
    )

    with pytest.raises(
        TypeError,
        match="DecisionIntelligenceResult",
    ):
        builder.build_from_result(
            {}
        )  # type: ignore[arg-type]
