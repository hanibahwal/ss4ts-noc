from __future__ import annotations

from ipaddress import IPv4Address
import os
from typing import Any

from app.services.routeros import (
    get_system_snapshot,
)


SERVICE_NAME = (
    "SS4TS Controlled RouterOS "
    "Read-Only Adapter"
)

SERVICE_VERSION = "1.1.0-H32.5.4"

CONTROLLED_EXECUTION_ENV = (
    "SS4TS_CONTROLLED_EXECUTION_ENABLED"
)

REAL_DEVICE_READ_ENV = (
    "SS4TS_REAL_DEVICE_READ_ENABLED"
)

CANARY_ALLOWLIST_ENV = (
    "SS4TS_CANARY_ROUTER_ALLOWLIST"
)

ALLOWED_ACTION = "CHECK_SYSTEM_RESOURCE"


def _enabled(name: str) -> bool:
    return (
        os.getenv(
            name,
            "false",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def _response(
    *,
    status: str,
    router_ip: str,
    action_type: str,
    reason: str,
    network_io_performed: bool = False,
    network_io_attempted: bool = False,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "engine": {
            "name": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
        "execution": {
            "status": status,
            "mode": "CANARY_READ_ONLY",
            "router_ip": router_ip,
            "action_type": action_type,
            "reason": reason,
            "network_io_attempted":
                network_io_attempted,
            "network_io_performed":
                network_io_performed,
            "device_command_executed":
                False,
            "configuration_changed":
                False,
            "read_only":
                True,
            "snapshot":
                snapshot,
        },
        "safety": {
            "controlled_execution_required":
                True,
            "real_device_read_required":
                True,
            "canary_allowlist_required":
                True,
            "device_command_execution":
                False,
            "configuration_write":
                False,
            "credentials_exposed":
                False,
        },
    }


def _canary_routers() -> frozenset[str]:
    raw_value = os.getenv(
        CANARY_ALLOWLIST_ENV,
        "",
    ).strip()

    if not raw_value:
        return frozenset()

    routers: set[str] = set()

    for raw_item in raw_value.split(","):
        item = raw_item.strip()

        if not item:
            continue

        try:
            routers.add(
                str(
                    IPv4Address(
                        item
                    )
                )
            )
        except ValueError as exc:
            raise ValueError(
                "Canary router allowlist "
                "contains an invalid IPv4 address"
            ) from exc

    return frozenset(
        routers
    )


def preflight_canary_read(
    *,
    router_ip: str,
    action_type: str,
) -> dict[str, Any]:
    """
    Validate every canary prerequisite without
    performing RouterOS or other network I/O.
    """
    requested_router = str(
        router_ip
    ).strip()

    requested_action = str(
        action_type
    ).strip()

    try:
        validated_router = str(
            IPv4Address(
                requested_router
            )
        )
    except ValueError:
        return _response(
            status="REJECTED",
            router_ip=requested_router,
            action_type=requested_action,
            reason="Invalid router IPv4 address",
        )

    if (
        requested_action
        != ALLOWED_ACTION
    ):
        return _response(
            status="REJECTED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=(
                "Action is not included in the "
                "read-only canary allowlist"
            ),
        )

    if not _enabled(
        CONTROLLED_EXECUTION_ENV
    ):
        return _response(
            status="DISABLED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=(
                "Controlled execution is disabled"
            ),
        )

    if not _enabled(
        REAL_DEVICE_READ_ENV
    ):
        return _response(
            status="DISABLED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=(
                "Real-device read access is disabled"
            ),
        )

    try:
        allowed_routers = (
            _canary_routers()
        )
    except ValueError as exc:
        return _response(
            status="REJECTED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=str(exc),
        )

    if not allowed_routers:
        return _response(
            status="REJECTED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=(
                "Canary router allowlist is empty"
            ),
        )

    if (
        validated_router
        not in allowed_routers
    ):
        return _response(
            status="REJECTED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=(
                "Router is not included in the "
                "canary allowlist"
            ),
        )

    return _response(
        status="READY",
        router_ip=validated_router,
        action_type=requested_action,
        reason=(
            "Read-only RouterOS canary "
            "preflight passed"
        ),
    )


def execute_canary_read(
    *,
    router_ip: str,
    action_type: str,
) -> dict[str, Any]:
    preflight = preflight_canary_read(
        router_ip=router_ip,
        action_type=action_type,
    )

    preflight_execution = (
        preflight.get(
            "execution",
            {},
        )
    )

    if (
        preflight_execution.get(
            "status"
        )
        != "READY"
    ):
        return preflight

    validated_router = str(
        preflight_execution[
            "router_ip"
        ]
    )

    requested_action = str(
        preflight_execution[
            "action_type"
        ]
    )

    try:
        snapshot = get_system_snapshot(
            validated_router
        )
    except Exception as exc:
        return _response(
            status="FAILED",
            router_ip=validated_router,
            action_type=requested_action,
            reason=(
                "Read-only RouterOS probe failed: "
                f"{exc.__class__.__name__}"
            ),
            network_io_attempted=True,
            network_io_performed=True,
        )

    return _response(
        status="READ_ONLY_SUCCESS",
        router_ip=validated_router,
        action_type=requested_action,
        reason=(
            "Read-only RouterOS canary probe "
            "completed"
        ),
        network_io_attempted=True,
        network_io_performed=True,
        snapshot=snapshot,
    )
