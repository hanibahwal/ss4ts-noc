from __future__ import annotations

import asyncio

from pathlib import Path

from app.api.v1 import (
    controlled_execution_production_readiness as api,
)
from app.api.v1.router import (
    api_router,
)
from app.services.controlled_execution_production_readiness import (
    ControlledExecutionProductionReadiness,
    REQUIRED_COMPONENTS,
)


def run(
    coroutine,
):
    return asyncio.run(
        coroutine
    )


def test_readiness_is_ready_with_valid_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    monkeypatch.delenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        raising=False,
    )

    service = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
    )

    result = service.evaluate()

    assert result["status"] == "ready"
    assert result["accepted"] is True

    assert (
        result["database"][
            "database_reachable"
        ]
        is True
    )

    assert (
        result["database"][
            "database_writable"
        ]
        is True
    )

    assert (
        result["database"]["integrity"]
        == "ok"
    )


def test_safe_defaults_are_required(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    monkeypatch.delenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        raising=False,
    )

    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    assert (
        result["configuration"][
            "safe_default_execution_disabled"
        ]
        is True
    )

    assert (
        result["configuration"][
            "safe_default_runtime_disabled"
        ]
        is True
    )


def test_enabled_execution_is_not_accepted_as_safe_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    monkeypatch.delenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        raising=False,
    )

    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    assert result["status"] == "not_ready"
    assert result["accepted"] is False

    assert (
        "CE-READY-005"
        in result["acceptance"][
            "failed_check_ids"
        ]
    )


def test_enabled_runtime_is_not_accepted_as_safe_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        "true",
    )

    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    assert result["status"] == "not_ready"

    assert (
        "CE-READY-006"
        in result["acceptance"][
            "failed_check_ids"
        ]
    )


def test_invalid_database_parent_is_not_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    monkeypatch.delenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        raising=False,
    )

    invalid_parent = (
        tmp_path
        / "not-a-directory"
    )

    invalid_parent.write_text(
        "file"
    )

    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                invalid_parent
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    assert result["status"] == "not_ready"
    assert result["accepted"] is False

    assert (
        result["database"][
            "database_reachable"
        ]
        is False
    )

    assert (
        result["database"][
            "database_writable"
        ]
        is False
    )


def test_required_components_manifest(
    tmp_path: Path,
) -> None:
    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    assert (
        result["components"]["count"]
        == len(
            REQUIRED_COMPONENTS
        )
    )

    assert (
        result["components"]["complete"]
        is True
    )

    assert (
        "controlled_execution_security_validation"
        in result["components"]["required"]
    )


def test_safety_evidence_is_fail_closed(
    tmp_path: Path,
) -> None:
    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    safety = result["safety"]

    assert safety["readiness_only"] is True
    assert safety["fail_closed"] is True
    assert safety["simulation_only"] is True
    assert safety["approval_claimed"] is False
    assert safety["execution_started"] is False
    assert safety["runtime_started"] is False
    assert safety["network_io_performed"] is False
    assert safety["device_command_executed"] is False
    assert safety["credentials_exposed"] is False


def test_release_candidate_when_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    monkeypatch.delenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        raising=False,
    )

    result = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
        .evaluate()
    )

    assert (
        result["release"][
            "release_candidate"
        ]
        is True
    )

    assert (
        result["release"][
            "next_gate"
        ]
        == "H23_FINAL_INTEGRATION"
    )


def test_readiness_api(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = (
        ControlledExecutionProductionReadiness(
            receipt_database=(
                tmp_path
                / "controlled-receipts.db"
            )
        )
    )

    monkeypatch.setattr(
        api,
        "evaluate_controlled_execution_readiness",
        service.evaluate,
    )

    result = run(
        api.controlled_execution_readiness()
    )

    assert result["component"] == (
        "controlled-execution"
    )

    assert result["status"] == "ready"

    assert (
        result["safety"][
            "receipt_payloads_exposed"
        ]
        is False
    )


def test_readiness_route_registered(
) -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/remediation/"
        "controlled-execution/"
        "readiness"
        in paths
    )
