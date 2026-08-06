from __future__ import annotations

from typing import Any

from app.services.legacy_execution_containment import (
    execute_legacy_compatibility_path,
)


ENGINE_NAME = (
    "SS4TS AI Safe Remediation Executor"
)

ENGINE_VERSION = "2.0.0-contained"


def execute_remediation(
    *,
    approval_id: str,
) -> dict[str, Any]:
    """
    Deprecated compatibility entry point.

    Execution is delegated to the controlled gate. This module no
    longer opens an independent database execution workflow.
    """
    return execute_legacy_compatibility_path(
        approval_id=approval_id,
        legacy_entry_point=(
            "execute_remediation"
        ),
    )
