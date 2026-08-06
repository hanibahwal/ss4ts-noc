from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.decision_execution_runtime import (
    DecisionExecutionRuntime,
    runtime,
)


def test_runtime_readiness_initializes_database(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "decision-runtime.db"
    )

    decision_runtime = (
        DecisionExecutionRuntime(
            database
        )
    )

    readiness = (
        decision_runtime.readiness()
    )

    assert readiness["status"] == "ready"
    assert readiness["initialized"] is True

    assert (
        readiness["database_reachable"]
        is True
    )

    assert (
        readiness["database_writable"]
        is True
    )

    assert readiness["integrity"] == "ok"
    assert readiness["record_count"] == 0
    assert readiness["persistent"] is True
    assert database.exists()


def test_runtime_readiness_reports_records(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "decision-runtime.db"
    )

    decision_runtime = (
        DecisionExecutionRuntime(
            database
        )
    )

    decision_runtime.initialize()

    with decision_runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO decision_execution_runtime (
                authorization_id,
                decision_id,
                plan_id,
                source_node_id,
                action_payload,
                plan_payload,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "authorization:readiness",
                "decision:readiness",
                "plan:readiness",
                "node:readiness",
                "{}",
                "{}",
                "2026-08-06T00:00:00+00:00",
                "2026-08-06T00:00:00+00:00",
            ),
        )

        connection.commit()

    readiness = (
        decision_runtime.readiness()
    )

    assert readiness["status"] == "ready"
    assert readiness["record_count"] == 1


def test_runtime_readiness_failure_is_safe(
    tmp_path,
) -> None:
    invalid_parent = (
        tmp_path
        / "not-a-directory"
    )

    invalid_parent.write_text(
        "file"
    )

    decision_runtime = (
        DecisionExecutionRuntime(
            invalid_parent
            / "decision-runtime.db"
        )
    )

    readiness = (
        decision_runtime.readiness()
    )

    assert (
        readiness["status"]
        == "not_ready"
    )

    assert (
        readiness["database_reachable"]
        is False
    )

    assert (
        readiness["database_writable"]
        is False
    )

    assert (
        readiness[
            "network_io_performed"
        ]
        is False
    )

    assert (
        readiness[
            "device_command_executed"
        ]
        is False
    )


def test_readiness_api(
    tmp_path,
    monkeypatch,
) -> None:
    database = (
        tmp_path
        / "decision-runtime.db"
    )

    monkeypatch.setenv(
        "SS4TS_DECISION_RUNTIME_DB",
        str(database),
    )

    runtime.clear()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/"
            "decision-executions/"
            "readiness"
        )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["component"]
        == "decision-execution-runtime"
    )

    assert payload["status"] == "ready"
    assert payload["initialized"] is True
    assert payload["integrity"] == "ok"

    assert (
        payload["safety"][
            "payloads_exposed"
        ]
        is False
    )

    assert (
        payload["safety"][
            "lease_tokens_exposed"
        ]
        is False
    )


def test_lifespan_initializes_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    database = (
        tmp_path
        / "startup-runtime.db"
    )

    monkeypatch.setenv(
        "SS4TS_DECISION_RUNTIME_DB",
        str(database),
    )

    with TestClient(app):
        assert database.exists()

        assert (
            app.state
            .decision_execution_runtime
            is runtime
        )

        readiness = (
            app.state
            .decision_execution_runtime
            .readiness()
        )

        assert (
            readiness["status"]
            == "ready"
        )
