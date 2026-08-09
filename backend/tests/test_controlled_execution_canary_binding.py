from __future__ import annotations

from app.services import (
    controlled_execution_gate as gate,
)
from app.services import (
    remediation_approval_service,
)
from app.services.controlled_execution_receipt_store import (
    ControlledExecutionReceiptStore,
)


ROUTER_IP = "192.168.88.1"

ACTION = "CHECK_SYSTEM_RESOURCE"


def _enable_canary(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_REAL_DEVICE_READ_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_CANARY_ROUTER_ALLOWLIST",
        ROUTER_IP,
    )


def _use_databases(
    tmp_path,
    monkeypatch,
):
    approval_database = (
        tmp_path
        / "approvals.db"
    )

    monkeypatch.setattr(
        remediation_approval_service,
        "DB_PATH",
        approval_database,
    )

    remediation_approval_service._init_db()

    receipt_store = (
        ControlledExecutionReceiptStore(
            tmp_path
            / "receipts.db"
        )
    )

    monkeypatch.setattr(
        gate,
        "receipt_store",
        receipt_store,
    )

    return receipt_store


def _approved_canary() -> dict:
    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip=ROUTER_IP,
            action_type=ACTION,
            reason=(
                "H32.5.3 controlled "
                "read-only canary"
            ),
        )
    )

    intent = created[
        "intent"
    ]

    assert (
        intent["execution_class"]
        == "READ_ONLY"
    )

    assert intent["read_only"] is True

    assert (
        intent["verification_required"]
        is True
    )

    assert (
        intent["rollback_required"]
        is False
    )

    approval_id = (
        created["approval"][
            "approval_id"
        ]
    )

    approved = (
        remediation_approval_service
        .approve_request(
            approval_id
        )
    )

    assert (
        approved["success"]
        is True
    )

    return approved[
        "approval"
    ]


def test_canary_intent_is_read_only(
    tmp_path,
    monkeypatch,
) -> None:
    _use_databases(
        tmp_path,
        monkeypatch,
    )

    approval = (
        _approved_canary()
    )

    assert (
        approval["execution_class"]
        == "READ_ONLY"
    )

    assert (
        approval["read_only"]
        is True
    )

    assert (
        approval["rollback_required"]
        is False
    )


def test_approved_canary_read_success(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_databases(
        tmp_path,
        monkeypatch,
    )

    _enable_canary(
        monkeypatch
    )

    approval = (
        _approved_canary()
    )

    calls: list[
        tuple[str, str]
    ] = []

    def fake_canary_read(
        *,
        router_ip: str,
        action_type: str,
    ) -> dict:
        calls.append(
            (
                router_ip,
                action_type,
            )
        )

        return {
            "execution": {
                "status":
                    "READ_ONLY_SUCCESS",
                "reason":
                    "Mocked canary success",
                "network_io_attempted":
                    True,
                "network_io_performed":
                    True,
                "device_command_executed":
                    False,
                "configuration_changed":
                    False,
                "read_only":
                    True,
                "snapshot": {
                    "identity":
                        "mock-canary",
                    "cpu_usage":
                        17.0,
                },
            }
        }

    monkeypatch.setattr(
        gate,
        "execute_canary_read",
        fake_canary_read,
    )

    result = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    execution = result[
        "execution"
    ]

    assert calls == [
        (
            ROUTER_IP,
            ACTION,
        )
    ]

    assert (
        execution["status"]
        == "READ_ONLY_SUCCESS"
    )

    assert (
        execution["mode"]
        == "CANARY_READ_ONLY"
    )

    assert (
        execution[
            "network_io_performed"
        ]
        is True
    )

    assert (
        execution[
            "device_command_executed"
        ]
        is False
    )

    assert (
        execution[
            "configuration_changed"
        ]
        is False
    )

    assert (
        execution["read_only"]
        is True
    )

    stored_approval = (
        remediation_approval_service
        .get_approval_by_id(
            approval[
                "approval_id"
            ]
        )
    )

    assert (
        stored_approval["status"]
        == "EXECUTED"
    )

    receipt = store.get(
        execution[
            "execution_id"
        ]
    )

    assert (
        receipt.mode
        == "CANARY_READ_ONLY"
    )

    assert (
        receipt.status
        == "READ_ONLY_SUCCESS"
    )

    assert (
        receipt.network_io_performed
        is True
    )

    assert (
        receipt.device_command_executed
        is False
    )


def test_failed_canary_does_not_become_executed(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_databases(
        tmp_path,
        monkeypatch,
    )

    _enable_canary(
        monkeypatch
    )

    approval = (
        _approved_canary()
    )

    def fake_canary_read(
        *,
        router_ip: str,
        action_type: str,
    ) -> dict:
        return {
            "execution": {
                "status":
                    "FAILED",
                "reason":
                    "Mocked probe failure",
                "network_io_attempted":
                    True,
                "network_io_performed":
                    True,
                "device_command_executed":
                    False,
                "configuration_changed":
                    False,
                "read_only":
                    True,
                "snapshot":
                    None,
            }
        }

    monkeypatch.setattr(
        gate,
        "execute_canary_read",
        fake_canary_read,
    )

    result = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    execution = result[
        "execution"
    ]

    assert (
        execution["status"]
        == "FAILED"
    )

    stored_approval = (
        remediation_approval_service
        .get_approval_by_id(
            approval[
                "approval_id"
            ]
        )
    )

    assert (
        stored_approval["status"]
        == "EXECUTION_FAILED"
    )

    receipt = store.get(
        execution[
            "execution_id"
        ]
    )

    assert receipt.status == "FAILED"

    assert (
        receipt.network_io_performed
        is True
    )

    assert (
        receipt.device_command_executed
        is False
    )


def test_canary_approval_is_single_use(
    tmp_path,
    monkeypatch,
) -> None:
    _use_databases(
        tmp_path,
        monkeypatch,
    )

    _enable_canary(
        monkeypatch
    )

    approval = (
        _approved_canary()
    )

    calls = {
        "count": 0,
    }

    def fake_canary_read(
        *,
        router_ip: str,
        action_type: str,
    ) -> dict:
        calls["count"] += 1

        return {
            "execution": {
                "status":
                    "READ_ONLY_SUCCESS",
                "reason":
                    "Mocked success",
                "network_io_attempted":
                    True,
                "network_io_performed":
                    True,
                "snapshot":
                    {},
            }
        }

    monkeypatch.setattr(
        gate,
        "execute_canary_read",
        fake_canary_read,
    )

    first = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    second = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    assert (
        first["execution"]["status"]
        == "READ_ONLY_SUCCESS"
    )

    assert (
        second["execution"]["status"]
        == "REJECTED"
    )

    assert calls["count"] == 1


def test_real_device_read_disabled_does_not_claim(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_databases(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    monkeypatch.delenv(
        "SS4TS_REAL_DEVICE_READ_ENABLED",
        raising=False,
    )

    monkeypatch.setenv(
        "SS4TS_CANARY_ROUTER_ALLOWLIST",
        ROUTER_IP,
    )

    approval = _approved_canary()

    called = {
        "value": False,
    }

    def should_not_execute(
        **kwargs,
    ) -> dict:
        called["value"] = True
        raise AssertionError(
            "Canary execution must not run"
        )

    monkeypatch.setattr(
        gate,
        "execute_canary_read",
        should_not_execute,
    )

    result = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    execution = result["execution"]

    assert execution["status"] == "DISABLED"
    assert execution["approval_consumed"] is False
    assert execution["network_io_attempted"] is False
    assert execution["network_io_performed"] is False
    assert called["value"] is False

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "APPROVED"

    assert (
        store.by_approval(
            approval["approval_id"]
        )
        == []
    )


def test_empty_canary_allowlist_does_not_claim(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_databases(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_REAL_DEVICE_READ_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_CANARY_ROUTER_ALLOWLIST",
        "",
    )

    approval = _approved_canary()

    result = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        result["execution"][
            "approval_consumed"
        ]
        is False
    )

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "APPROVED"

    assert (
        store.by_approval(
            approval["approval_id"]
        )
        == []
    )


def test_non_allowlisted_router_does_not_claim(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_databases(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_REAL_DEVICE_READ_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_CANARY_ROUTER_ALLOWLIST",
        "192.168.88.2",
    )

    approval = _approved_canary()

    result = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        result["execution"][
            "network_io_attempted"
        ]
        is False
    )

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "APPROVED"

    assert (
        store.by_approval(
            approval["approval_id"]
        )
        == []
    )


def test_malformed_canary_allowlist_does_not_claim(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_databases(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_REAL_DEVICE_READ_ENABLED",
        "true",
    )

    monkeypatch.setenv(
        "SS4TS_CANARY_ROUTER_ALLOWLIST",
        (
            f"{ROUTER_IP},"
            "invalid-router"
        ),
    )

    approval = _approved_canary()

    result = (
        gate.execute_controlled_remediation(
            approval_id=
                approval["approval_id"],
        )
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "invalid IPv4"
        in result["execution"]["reason"]
    )

    stored = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert stored["status"] == "APPROVED"

    assert (
        store.by_approval(
            approval["approval_id"]
        )
        == []
    )
