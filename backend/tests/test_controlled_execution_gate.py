from __future__ import annotations

from app.services import (
    remediation_approval_service,
)
from app.services.controlled_execution_gate import (
    execute_controlled_remediation,
)


def _use_database(
    tmp_path,
    monkeypatch,
) -> None:
    database = (
        tmp_path
        / "remediation-approval.db"
    )

    monkeypatch.setattr(
        remediation_approval_service,
        "DB_PATH",
        database,
    )

    remediation_approval_service._init_db()


def _approved_request(
    *,
    router_ip: str = "192.168.88.1",
    action_type: str = "CHECK_CPU_PROCESS",
) -> dict:
    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip=router_ip,
            action_type=action_type,
            reason="Controlled execution test",
        )
    )

    approval_id = created[
        "approval"
    ]["approval_id"]

    approved = (
        remediation_approval_service
        .approve_request(
            approval_id
        )
    )

    assert approved["success"] is True

    return approved["approval"]


def test_gate_defaults_to_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    approval = _approved_request()

    result = execute_controlled_remediation(
        approval_id=approval["approval_id"],
    )

    execution = result["execution"]

    assert execution["status"] == "DISABLED"
    assert execution["execution_enabled"] is False
    assert execution["network_io_performed"] is False
    assert execution["device_command_executed"] is False

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "APPROVED"


def test_gate_rejects_router_mismatch(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = _approved_request()

    result = execute_controlled_remediation(
        approval_id=approval["approval_id"],
        requested_router_ip="10.0.0.1",
        requested_action_type=(
            "CHECK_CPU_PROCESS"
        ),
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "APPROVED"


def test_gate_rejects_action_mismatch(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = _approved_request()

    result = execute_controlled_remediation(
        approval_id=approval["approval_id"],
        requested_router_ip="192.168.88.1",
        requested_action_type=(
            "CHECK_FIREWALL_LOAD"
        ),
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )


def test_gate_rejects_non_allowlisted_action(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = _approved_request(
        action_type=(
            "RESTART_LTE_INTERFACE"
        ),
    )

    result = execute_controlled_remediation(
        approval_id=approval["approval_id"],
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "allowlist"
        in result["execution"]["reason"]
    )


def test_approval_is_consumed_once(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = _approved_request()

    first = execute_controlled_remediation(
        approval_id=approval["approval_id"],
    )

    second = execute_controlled_remediation(
        approval_id=approval["approval_id"],
    )

    assert (
        first["execution"]["status"]
        == "SIMULATED_SUCCESS"
    )

    assert (
        first["execution"][
            "approval_consumed"
        ]
        is True
    )

    assert (
        first["execution"][
            "network_io_performed"
        ]
        is False
    )

    assert (
        first["execution"][
            "device_command_executed"
        ]
        is False
    )

    assert (
        second["execution"]["status"]
        == "REJECTED"
    )

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "EXECUTED"


def test_atomic_claim_prevents_reuse(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    approval = _approved_request()

    first = (
        remediation_approval_service
        .claim_approval_for_execution(
            approval["approval_id"]
        )
    )

    second = (
        remediation_approval_service
        .claim_approval_for_execution(
            approval["approval_id"]
        )
    )

    assert first["claimed"] is True
    assert second["claimed"] is False

    assert (
        second["approval"]["status"]
        == "EXECUTING"
    )
