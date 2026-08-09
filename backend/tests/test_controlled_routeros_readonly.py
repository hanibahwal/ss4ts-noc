from __future__ import annotations

from app.services import (
    controlled_routeros_readonly as adapter,
)


ROUTER_IP = "192.168.88.1"

ACTION = "CHECK_SYSTEM_RESOURCE"


def _enable(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        adapter.CONTROLLED_EXECUTION_ENV,
        "true",
    )

    monkeypatch.setenv(
        adapter.REAL_DEVICE_READ_ENV,
        "true",
    )

    monkeypatch.setenv(
        adapter.CANARY_ALLOWLIST_ENV,
        ROUTER_IP,
    )


def test_controlled_execution_defaults_disabled(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        adapter.CONTROLLED_EXECUTION_ENV,
        raising=False,
    )

    monkeypatch.delenv(
        adapter.REAL_DEVICE_READ_ENV,
        raising=False,
    )

    monkeypatch.delenv(
        adapter.CANARY_ALLOWLIST_ENV,
        raising=False,
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    execution = result[
        "execution"
    ]

    assert execution["status"] == "DISABLED"
    assert called["value"] is False
    assert (
        execution[
            "network_io_performed"
        ]
        is False
    )
    assert (
        execution[
            "device_command_executed"
        ]
        is False
    )


def test_real_device_read_defaults_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        adapter.CONTROLLED_EXECUTION_ENV,
        "true",
    )

    monkeypatch.delenv(
        adapter.REAL_DEVICE_READ_ENV,
        raising=False,
    )

    monkeypatch.setenv(
        adapter.CANARY_ALLOWLIST_ENV,
        ROUTER_IP,
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    assert (
        result["execution"]["status"]
        == "DISABLED"
    )

    assert called["value"] is False


def test_invalid_router_is_rejected(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip="not-an-ip",
        action_type=ACTION,
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert called["value"] is False


def test_non_read_only_action_is_rejected(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type="REBOOT_ROUTER",
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert called["value"] is False


def test_empty_canary_allowlist_is_rejected(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    monkeypatch.setenv(
        adapter.CANARY_ALLOWLIST_ENV,
        "",
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert called["value"] is False


def test_non_canary_router_is_rejected(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    monkeypatch.setenv(
        adapter.CANARY_ALLOWLIST_ENV,
        "192.168.88.2",
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert called["value"] is False


def test_malformed_allowlist_fails_closed(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    monkeypatch.setenv(
        adapter.CANARY_ALLOWLIST_ENV,
        (
            "192.168.88.1,"
            "invalid-router"
        ),
    )

    called = {
        "value": False,
    }

    def snapshot(
        host: str,
    ) -> dict:
        called["value"] = True
        return {}

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "invalid IPv4"
        in result["execution"]["reason"]
    )

    assert called["value"] is False


def test_canary_read_uses_mocked_snapshot(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    calls: list[str] = []

    expected = {
        "identity": "canary-router",
        "cpu_usage": 21.0,
        "uptime": "1d2h",
    }

    def snapshot(
        host: str,
    ) -> dict:
        calls.append(
            host
        )
        return dict(
            expected
        )

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    execution = result[
        "execution"
    ]

    assert (
        execution["status"]
        == "READ_ONLY_SUCCESS"
    )

    assert calls == [
        ROUTER_IP
    ]

    assert (
        execution["snapshot"]
        == expected
    )

    assert (
        execution[
            "network_io_attempted"
        ]
        is True
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


def test_probe_failure_does_not_claim_success(
    monkeypatch,
) -> None:
    _enable(
        monkeypatch
    )

    def snapshot(
        host: str,
    ) -> dict:
        raise TimeoutError(
            "mock timeout"
        )

    monkeypatch.setattr(
        adapter,
        "get_system_snapshot",
        snapshot,
    )

    result = adapter.execute_canary_read(
        router_ip=ROUTER_IP,
        action_type=ACTION,
    )

    execution = result[
        "execution"
    ]

    assert execution["status"] == "FAILED"

    assert (
        execution[
            "network_io_attempted"
        ]
        is True
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

    assert execution["snapshot"] is None

    assert (
        "mock timeout"
        not in execution["reason"]
    )
