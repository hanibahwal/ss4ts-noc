from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services import (
    autonomous_remediation_controller,
    legacy_execution_containment,
    mikrotik_remediation_executor,
    remediation_controller,
    remediation_executor,
)


LEGACY_FILES = (
    "autonomous_remediation_controller.py",
    "mikrotik_remediation_executor.py",
    "remediation_controller.py",
    "remediation_executor.py",
)


def _service_path(
    filename: str,
) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / filename
    )


@pytest.fixture
def controlled_result() -> dict:
    return {
        "engine": {
            "name":
                "SS4TS Controlled Execution Safety Gate",
        },
        "execution": {
            "status": "DISABLED",
            "approval_id": "approval-1",
            "network_io_performed": False,
            "device_command_executed": False,
        },
    }


def test_containment_delegates_to_gate(
    monkeypatch,
    controlled_result,
) -> None:
    captured = {}

    def fake_gate(
        *,
        approval_id: str,
    ) -> dict:
        captured["approval_id"] = (
            approval_id
        )

        return {
            "engine": dict(
                controlled_result["engine"]
            ),
            "execution": dict(
                controlled_result["execution"]
            ),
        }

    monkeypatch.setattr(
        legacy_execution_containment,
        "execute_controlled_remediation",
        fake_gate,
    )

    with pytest.warns(
        DeprecationWarning
    ):
        result = (
            legacy_execution_containment
            .execute_legacy_compatibility_path(
                approval_id="approval-1",
                legacy_entry_point=(
                    "legacy-test"
                ),
            )
        )

    assert (
        captured["approval_id"]
        == "approval-1"
    )

    assert (
        result["execution"][
            "legacy_path_contained"
        ]
        is True
    )

    assert (
        result["execution"][
            "legacy_arguments_ignored"
        ]
        is True
    )

    assert (
        result["execution"][
            "network_io_performed"
        ]
        is False
    )

    assert (
        result["execution"][
            "device_command_executed"
        ]
        is False
    )


def test_empty_approval_id_fails_closed(
) -> None:
    result = (
        legacy_execution_containment
        .execute_legacy_compatibility_path(
            approval_id=" ",
            legacy_entry_point=(
                "legacy-test"
            ),
        )
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        result["execution"][
            "legacy_path_contained"
        ]
        is True
    )


@pytest.mark.parametrize(
    (
        "module",
        "function_name",
        "kwargs",
    ),
    [
        (
            autonomous_remediation_controller,
            "execute_approved_remediation",
            {
                "approval_id": "approval-1",
                "router_ip": "10.0.0.1",
                "action_type":
                    "RESTART_LTE_INTERFACE",
                "username": "admin",
                "password": "secret",
            },
        ),
        (
            mikrotik_remediation_executor,
            "execute_mikrotik_remediation",
            {
                "approval_id": "approval-1",
                "router_ip": "10.0.0.1",
                "action_type":
                    "RESTART_LTE_INTERFACE",
            },
        ),
        (
            remediation_controller,
            "execute_remediation_action",
            {
                "approval": {
                    "approval_id":
                        "approval-1",
                    "router_ip":
                        "10.0.0.1",
                    "action_type":
                        "RESTART_LTE_INTERFACE",
                },
            },
        ),
        (
            remediation_executor,
            "execute_remediation",
            {
                "approval_id": "approval-1",
            },
        ),
    ],
)
def test_legacy_wrappers_use_containment(
    monkeypatch,
    module,
    function_name,
    kwargs,
) -> None:
    captured = {}

    def fake_containment(
        *,
        approval_id: str,
        legacy_entry_point: str,
    ) -> dict:
        captured.update({
            "approval_id":
                approval_id,
            "legacy_entry_point":
                legacy_entry_point,
        })

        return {
            "execution": {
                "status": "DISABLED",
                "legacy_path_contained":
                    True,
            },
        }

    monkeypatch.setattr(
        module,
        "execute_legacy_compatibility_path",
        fake_containment,
    )

    function = getattr(
        module,
        function_name,
    )

    result = function(
        **kwargs
    )

    assert (
        captured["approval_id"]
        == "approval-1"
    )

    assert (
        result["execution"][
            "legacy_path_contained"
        ]
        is True
    )


@pytest.mark.parametrize(
    "filename",
    LEGACY_FILES,
)
def test_legacy_modules_do_not_import_routeros(
    filename: str,
) -> None:
    source = _service_path(
        filename
    ).read_text()

    tree = ast.parse(
        source
    )

    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imported_modules.add(
                node.module or ""
            )

    assert not any(
        "routeros_api_client"
        in module_name
        for module_name in imported_modules
    )


@pytest.mark.parametrize(
    "filename",
    LEGACY_FILES,
)
def test_legacy_modules_have_no_routeros_commands(
    filename: str,
) -> None:
    source = _service_path(
        filename
    ).read_text()

    forbidden_fragments = (
        "/system/",
        "/interface/",
        "/ip/firewall/",
        "create_routeros_client",
        "RouterOSAPIClient",
        ".connect(",
        ".execute(",
        ".backup(",
        ".rollback(",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
