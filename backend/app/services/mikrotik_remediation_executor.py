from __future__ import annotations

from typing import Any

from app.services.legacy_execution_containment import (
    execute_legacy_compatibility_path,
)


ENGINE_NAME = (
    "SS4TS MikroTik Automated "
    "Remediation Engine"
)

ENGINE_VERSION = "2.0.0-contained"


def execute_mikrotik_remediation(
    *,
    router_ip: str | None = None,
    action_type: str | None = None,
    approval_id: str,
) -> dict[str, Any]:
    """
    Deprecated compatibility entry point.

    Caller-provided router and action values are ignored.
    """
    del router_ip, action_type

    return execute_legacy_compatibility_path(
        approval_id=approval_id,
        legacy_entry_point=(
            "execute_mikrotik_remediation"
        ),
    )
