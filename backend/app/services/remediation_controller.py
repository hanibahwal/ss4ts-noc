from __future__ import annotations

from typing import Any

from app.services.legacy_execution_containment import (
    execute_legacy_compatibility_path,
)


SERVICE_NAME = (
    "SS4TS AI Remediation Controller"
)

SERVICE_VERSION = "2.0.0-contained"


def execute_remediation_action(
    *,
    approval: dict[str, Any],
) -> dict[str, Any]:
    """
    Deprecated compatibility entry point.

    Only approval_id is accepted as execution authority.
    """
    approval_id = str(
        approval.get(
            "approval_id",
            "",
        )
    ).strip()

    return execute_legacy_compatibility_path(
        approval_id=approval_id,
        legacy_entry_point=(
            "execute_remediation_action"
        ),
    )
