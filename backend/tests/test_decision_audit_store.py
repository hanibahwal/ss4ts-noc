from __future__ import annotations

import json
import sqlite3

import pytest

from app.models.decision_audit import (
    DecisionAuditRecord,
)
from app.services.decision_explanation import (
    build_decision_explanation,
)
from app.services.decision_trace import (
    build_decision_trace,
)
from app.services.decision_fusion import (
    fuse_graph_decision,
)
from app.services.decision_audit_store import (
    DecisionAuditStore,
    calculate_audit_checksum,
    canonical_json,
)
from app.services.execution_planner import (
    build_execution_plan,
)
from tests.test_decision_fusion import (
    make_graph,
)


def make_audit_content():
    graph = make_graph(
        power_alarm=True
    )

    result = fuse_graph_decision(
        graph,
        "device:core",
    )

    trace = build_decision_trace(
        graph,
        "device:core",
    )

    explanation = (
        build_decision_explanation(
            graph,
            "device:core",
        )
    )

    execution_plan = (
        build_execution_plan(
            graph,
            "device:core",
        )
    )

    return (
        result,
        trace,
        explanation,
        execution_plan,
    )


def test_canonical_json_is_deterministic() -> None:
    first = canonical_json({
        "b": 2,
        "a": 1,
    })

    second = canonical_json({
        "a": 1,
        "b": 2,
    })

    assert first == second


def test_checksum_is_deterministic() -> None:
    payload = {
        "trace_id": "trace:1",
    }

    first = calculate_audit_checksum(
        trace_payload=payload,
        explanation_payload={},
        execution_plan_payload={},
        simulation_payload={},
    )

    second = calculate_audit_checksum(
        trace_payload=payload,
        explanation_payload={},
        execution_plan_payload={},
        simulation_payload={},
    )

    assert first == second
    assert len(first) == 64


def test_create_and_get_record(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    created = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    loaded = store.get(
        created.audit_id
    )

    assert isinstance(
        loaded,
        DecisionAuditRecord,
    )

    assert loaded is not None
    assert loaded.audit_id == created.audit_id
    assert loaded.trace_id == trace.trace_id

    assert (
        loaded.primary_cause_id
        .startswith("cause:power:")
    )


def test_record_contains_all_payloads(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    record = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    assert record.trace_payload
    assert record.explanation_payload
    assert record.execution_plan_payload

    assert record.has_explanation is True

    assert (
        record.has_execution_plan
        is True
    )

    assert record.has_simulation is False


def test_record_checksum_verifies(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    record = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    assert store.verify(
        record.audit_id
    ) is True


def test_tampered_record_fails_verification(
    tmp_path,
) -> None:
    database = (
        tmp_path / "audit.db"
    )

    store = DecisionAuditStore(
        database
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    record = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    with sqlite3.connect(
        database
    ) as connection:
        payload = dict(
            record.trace_payload
        )

        payload["title"] = (
            "Tampered trace"
        )

        connection.execute(
            """
            UPDATE decision_audit_records
            SET trace_payload = ?
            WHERE audit_id = ?
            """,
            (
                json.dumps(payload),
                record.audit_id,
            ),
        )

        connection.commit()

    assert store.verify(
        record.audit_id
    ) is False


def test_list_records_filters_source(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    first = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    second_trace = trace.to_dict()
    second_trace["trace_id"] = "trace:other"
    second_trace["decision_id"] = (
        "decision:other"
    )
    second_trace["source_node_id"] = (
        "device:other"
    )

    store.create_record(
        trace=second_trace,
    )

    records = store.list_records(
        source_node_id=
            trace.source_node_id,
    )

    assert len(records) == 1

    assert (
        records[0].audit_id
        == first.audit_id
    )


def test_count_records(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    assert store.count() == 2

    assert (
        store.count(
            source_node_id=
                trace.source_node_id,
        )
        == 2
    )


def test_duplicate_audit_id_rejected(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
        audit_id="audit:fixed",
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        store.create_record(
            trace=trace,
            explanation=explanation,
            execution_plan=
                execution_plan,
            audit_id="audit:fixed",
        )


def test_missing_trace_identity_rejected(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    with pytest.raises(
        ValueError,
        match="trace_id",
    ):
        store.create_record(
            trace={}
        )


def test_delete_record(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    record = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    assert store.delete(
        record.audit_id
    ) is True

    assert store.get(
        record.audit_id
    ) is None


def test_metadata_confirms_no_execution(
    tmp_path,
) -> None:
    store = DecisionAuditStore(
        tmp_path / "audit.db"
    )

    (
        _,
        trace,
        explanation,
        execution_plan,
    ) = make_audit_content()

    record = store.create_record(
        trace=trace,
        explanation=explanation,
        execution_plan=
            execution_plan,
    )

    assert (
        record.metadata
        ["network_io_performed"]
        is False
    )

    assert (
        record.metadata
        ["device_command_executed"]
        is False
    )
