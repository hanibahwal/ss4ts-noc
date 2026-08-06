from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import warnings

from app.services.controlled_execution_gate import (
    execute_controlled_remediation,
)


SERVICE_NAME = (
    "SS4TS Legacy Execution Path Containment"
)

SERVICE_VERSION = "1.0.0-fail-closed"


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def execute_legacy_compatibility_path(
    *,
    approval_id: str,
    legacy_entry_point: str,
) -> dict[str, Any]:
    """
    Route a legacy execution request through the controlled gate.

    Security guarantees:
    - approval_id is the only execution authority;
    - caller-supplied router/action/credentials are ignored;
    - immutable intent remains the source of truth;
    - no direct RouterOS client is invoked;
    - controlled execution remains feature-flag protected;
    - simulation-only safety remains enforced.
    """
    normalized_approval_id = str(
        approval_id
    ).strip()

    normalized_entry_point = str(
        legacy_entry_point
    ).strip()

    if not normalized_approval_id:
        return {
            "engine": {
                "name": SERVICE_NAME,
                "version": SERVICE_VERSION,
            },
            "execution": {
                "status": "REJECTED",
                "reason": "approval_id is required",
                "legacy_entry_point":
                    normalized_entry_point,
                "legacy_path_contained": True,
                "network_io_performed": False,
                "device_command_executed": False,
                "created_at": _utc_now(),
            },
        }

    warnings.warn(
        (
            f"{normalized_entry_point} is deprecated; "
            "execution was routed through the "
            "Controlled Execution Safety Gate"
        ),
        DeprecationWarning,
        stacklevel=2,
    )

    result = execute_controlled_remediation(
        approval_id=normalized_approval_id,
    )

    execution = result.setdefault(
        "execution",
        {},
    )

    execution.update({
        "legacy_entry_point":
            normalized_entry_point,
        "legacy_path_contained":
            True,
        "legacy_arguments_ignored":
            True,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    })

    result["containment"] = {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "policy": (
            "APPROVAL_ID_ONLY_CONTROLLED_GATE"
        ),
        "direct_routeros_access":
            False,
    }

    return result
