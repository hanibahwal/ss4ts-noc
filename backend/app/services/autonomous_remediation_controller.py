from __future__ import annotations

from typing import Any

from app.services.legacy_execution_containment import (
    execute_legacy_compatibility_path,
)


ENGINE_NAME = (
    "SS4TS Autonomous Remediation "
    "Execution Controller"
)

ENGINE_VERSION = "2.0.0-contained"


def execute_approved_remediation(
    *,
    approval_id: str,
    router_ip: str | None = None,
    action_type: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """
    Deprecated compatibility entry point.

    router_ip, action_type, username and password are intentionally
    ignored. The immutable persisted execution intent is authoritative.
    """
    del (
        router_ip,
        action_type,
        username,
        password,
    )

    return execute_legacy_compatibility_path(
        approval_id=approval_id,
        legacy_entry_point=(
            "execute_approved_remediation"
        ),
    )
