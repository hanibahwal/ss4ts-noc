from __future__ import annotations

import pytest

from app.models.decision_trace import (
    DecisionTrace,
    DecisionTraceStage,
    DecisionTraceStageStatus,
    DecisionTraceStageType,
    normalize_decision_trace,
)


def make_stage(
    *,
    stage_id: str = "stage:1",
    sequence: int = 1,
    stage_type: DecisionTraceStageType = (
        DecisionTraceStageType.TELEMETRY
    ),
    selected: bool = False,
) -> DecisionTraceStage:
    return DecisionTraceStage(
        stage_id=stage_id,
        sequence=sequence,
        stage_type=stage_type,
        title="Trace stage",
        description="A decision processing stage.",
        status=(
            DecisionTraceStageStatus.COMPLETED
        ),
        confidence_percent=90,
        selected=selected,
        input_ids=["input:1"],
        output_ids=["output:1"],
        evidence_ids=["evidence:1"],
    )


def test_stage_serialization() -> None:
    stage = make_stage()

    payload = stage.to_dict()

    assert payload["id"] == "stage:1"
    assert payload["type"] == "telemetry"
    assert payload["confidence"] == 90.0
    assert payload["selected"] is False


def test_stage_from_dict_aliases() -> None:
    stage = DecisionTraceStage.from_dict({
        "id": "stage:root-cause",
        "order": 2,
        "type": "root_cause",
        "title": "Root cause",
        "summary": "Cause ranked.",
        "status": "selected",
        "confidence": 96,
        "selected": True,
    })

    assert (
        stage.stage_type
        == DecisionTraceStageType.ROOT_CAUSE
    )

    assert (
        stage.status
        == DecisionTraceStageStatus.SELECTED
    )

    assert stage.selected is True


def test_invalid_sequence_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="sequence",
    ):
        make_stage(
            sequence=0
        )


def test_trace_sorts_stages() -> None:
    trace = DecisionTrace(
        trace_id="trace:1",
        decision_id="decision:1",
        source_node_id="device:core",
        title="Decision trace",
        stages=[
            make_stage(
                stage_id="stage:2",
                sequence=2,
            ),
            make_stage(
                stage_id="stage:1",
                sequence=1,
            ),
        ],
    )

    assert [
        stage.sequence
        for stage in trace.stages
    ] == [1, 2]


def test_trace_statistics() -> None:
    trace = DecisionTrace(
        trace_id="trace:1",
        decision_id="decision:1",
        source_node_id="device:core",
        title="Decision trace",
        stages=[
            make_stage(
                stage_id="stage:1",
                sequence=1,
            ),
            make_stage(
                stage_id="stage:2",
                sequence=2,
                selected=True,
            ),
        ],
    )

    payload = trace.to_dict()

    assert (
        payload["statistics"]
        ["stage_count"]
        == 2
    )

    assert (
        payload["statistics"]
        ["selected_stage_count"]
        == 1
    )


def test_trace_final_stage() -> None:
    trace = DecisionTrace(
        trace_id="trace:1",
        decision_id="decision:1",
        source_node_id="device:core",
        title="Decision trace",
        stages=[
            make_stage(
                stage_id="stage:1",
                sequence=1,
            ),
            make_stage(
                stage_id="stage:2",
                sequence=2,
            ),
        ],
    )

    assert trace.final_stage is not None

    assert (
        trace.final_stage.stage_id
        == "stage:2"
    )


def test_duplicate_stage_ids_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate stage ids",
    ):
        DecisionTrace(
            trace_id="trace:1",
            decision_id="decision:1",
            source_node_id="device:core",
            title="Decision trace",
            stages=[
                make_stage(
                    stage_id="stage:1",
                    sequence=1,
                ),
                make_stage(
                    stage_id="stage:1",
                    sequence=2,
                ),
            ],
        )


def test_duplicate_sequences_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate sequences",
    ):
        DecisionTrace(
            trace_id="trace:1",
            decision_id="decision:1",
            source_node_id="device:core",
            title="Decision trace",
            stages=[
                make_stage(
                    stage_id="stage:1",
                    sequence=1,
                ),
                make_stage(
                    stage_id="stage:2",
                    sequence=1,
                ),
            ],
        )


def test_read_only_trace_rejects_execution() -> None:
    with pytest.raises(
        ValueError,
        match="Read-only",
    ):
        DecisionTrace(
            trace_id="trace:1",
            decision_id="decision:1",
            source_node_id="device:core",
            title="Decision trace",
            read_only=True,
            device_command_executed=True,
        )


def test_trace_from_dict() -> None:
    trace = DecisionTrace.from_dict({
        "id": "trace:1",
        "decision_id": "decision:1",
        "source": "device:core",
        "title": "Decision trace",
        "stages": [],
    })

    assert trace.trace_id == "trace:1"
    assert trace.source_node_id == "device:core"


def test_normalize_decision_trace() -> None:
    trace = normalize_decision_trace({
        "id": "trace:1",
        "decision_id": "decision:1",
        "source": "device:core",
        "title": "Decision trace",
        "stages": [],
    })

    assert isinstance(
        trace,
        DecisionTrace,
    )


def test_normalize_invalid_trace() -> None:
    assert (
        normalize_decision_trace(
            "invalid"
        )
        is None
    )
