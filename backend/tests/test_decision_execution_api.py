from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from app.api.v1 import (
    autonomous_shadow,
    decision_executions,
)
from app.api.v1.router import (
    api_router,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
)
from app.services.decision_execution_runtime import (
    runtime,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.shadow_decision_store import (
    ShadowDecisionStore,
)
from tests.test_execution_simulator import (
    make_plan,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


@pytest.fixture
def execution_environment(
    tmp_path,
    monkeypatch,
):
    authorization_database = (
        tmp_path
        / "execution-authorization.db"
    )

    audit_database = (
        tmp_path
        / "decision-audit.db"
    )

    runtime_database = (
        tmp_path
        / "decision-execution-runtime.db"
    )

    shadow_database = (
        tmp_path
        / "shadow-decisions.db"
    )

    monkeypatch.setenv(
        "SS4TS_EXECUTION_AUTH_DB",
        str(authorization_database),
    )

    monkeypatch.setenv(
        "SS4TS_DECISION_AUDIT_DB",
        str(audit_database),
    )

    monkeypatch.setenv(
        "SS4TS_DECISION_RUNTIME_DB",
        str(runtime_database),
    )

    monkeypatch.setenv(
        "SS4TS_SHADOW_DECISION_DB",
        str(shadow_database),
    )

    runtime.clear()

    yield {
        "authorization_database":
            authorization_database,
        "audit_database":
            audit_database,
        "runtime_database":
            runtime_database,
        "shadow_database":
            shadow_database,
    }

    runtime.clear()


def prepare_payload():
    plan = make_plan()

    return (
        decision_executions
        .PrepareDecisionExecutionPayload(
            incident_id=(
                "incident:decision-api-001"
            ),
            problem=(
                "Primary interface instability"
            ),
            recommendation=(
                "Simulate failover and verify "
                "backup connectivity"
            ),
            confidence_percent=95,
            risk_level="high",
            execution_mode=(
                "approval_required"
            ),
            target=(
                decision_executions
                .TargetPayload(
                    router_ip="192.168.88.1",
                    interface_name="ether1",
                    site_id="site:riyadh",
                    device_id=(
                        "device:router-01"
                    ),
                )
            ),
            command=(
                decision_executions
                .CommandPayload(
                    action_type=(
                        "disable_interface"
                    ),
                    parameters={
                        "interface": "ether1",
                    },
                    rollback_action_type=(
                        "enable_interface"
                    ),
                    rollback_parameters={
                        "interface": "ether1",
                    },
                    verification_steps=[
                        (
                            "verify_interface_"
                            "disabled"
                        ),
                        (
                            "verify_backup_link_"
                            "active"
                        ),
                    ],
                )
            ),
            requester=(
                decision_executions
                .IdentityPayload(
                    identity_id="user:hani",
                    display_name="Hani",
                    role=(
                        ApprovalRole
                        .NETWORK_ENGINEER
                    ),
                )
            ),
            plan=plan.to_dict(),
            requested_by=(
                "decision-execution-api-test"
            ),
        )
    )


def simulate_payload(
    *,
    owner_id: str = "worker:api-test",
    fail_step_ids: list[str] | None = None,
):
    return (
        decision_executions
        .SimulateDecisionExecutionPayload(
            owner_id=owner_id,
            lease_ttl_seconds=60,
            fail_step_ids=(
                fail_step_ids or []
            ),
            trace_id=(
                "trace:decision-api-test"
            ),
        )
    )


def approve_authorization(
    authorization_id: str,
    database,
) -> None:
    store = ExecutionAuthorizationStore(
        database
    )

    store.approve_atomic(
        authorization_id,
        approver=ApprovalIdentity(
            identity_id="user:senior",
            display_name="Senior Engineer",
            role=(
                ApprovalRole
                .SENIOR_ENGINEER
            ),
        ),
        expected_version=(
            store.get_record_version(
                authorization_id
            )
        ),
        idempotency_key=(
            "approve-decision-api-001"
        ),
    )


def test_prepare_decision_execution(
    execution_environment,
) -> None:
    result = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    assert result["prepared"] is True

    assert (
        result["authorization"]["status"]
        == "pending"
    )

    assert (
        result["runtime"]["action"]["status"]
        == "pending_approval"
    )

    assert (
        result["safety"]
        ["device_command_executed"]
        is False
    )

    assert runtime.count() == 1


def test_prepare_overrides_plan_decision_id(
    execution_environment,
) -> None:
    payload = prepare_payload()

    payload.plan["decision_id"] = (
        "decision:client-supplied"
    )

    result = run(
        decision_executions
        .prepare_decision_execution(
            payload
        )
    )

    action_decision_id = (
        result["runtime"]["action"]
        ["decision_id"]
    )

    assert (
        result["runtime"]["plan"]
        ["decision_id"]
        == action_decision_id
    )

    assert (
        action_decision_id
        != "decision:client-supplied"
    )


def test_simulate_approved_execution(
    execution_environment,
) -> None:
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    approve_authorization(
        authorization_id,
        execution_environment[
            "authorization_database"
        ],
    )

    result = run(
        decision_executions
        .simulate_decision_execution(
            authorization_id,
            simulate_payload(),
        )
    )

    assert (
        result["execution"]["action"]
        ["status"]
        == "completed"
    )

    assert (
        result["execution"]["simulation"]
        ["status"]
        == "completed"
    )

    assert (
        result["execution"]["lease"]
        ["status"]
        == "released"
    )

    assert (
        result["evidence"]["verified"]
        is True
    )

    assert (
        result["safety"]
        ["audit_verified"]
        is True
    )


def test_simulation_creates_shadow_record(
    execution_environment,
) -> None:
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    approve_authorization(
        authorization_id,
        execution_environment[
            "authorization_database"
        ],
    )

    result = run(
        decision_executions
        .simulate_decision_execution(
            authorization_id,
            simulate_payload(),
        )
    )

    assert result["shadow"]["captured"] is True
    assert (
        result["shadow"]["dry_run_only"]
        is True
    )
    assert (
        result["shadow"][
            "execution_authority"
        ]
        is False
    )
    assert (
        result["shadow"][
            "device_command_executed"
        ]
        is False
    )

    store = ShadowDecisionStore(
        execution_environment[
            "shadow_database"
        ]
    )

    records = store.list_recent(
        limit=10
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.decision_id
        == prepared["runtime"]["action"]
        ["decision_id"]
    )

    assert (
        record.source_node_id
        == "device:router-01"
    )

    assert (
        record.proposed_action
        == "disable_interface"
    )

    assert (
        record.confidence_percent
        == 95
    )

    assert record.risk_level == "HIGH"
    assert record.dry_run_only is True


def test_shadow_outcome_comparison_end_to_end(
    execution_environment,
) -> None:
    """
    H32.3 end-to-end validation:

    Decision
      -> approved dry-run simulation
      -> automatic shadow capture
      -> verified execution evidence
      -> prediction vs observed outcome comparison.

    No managed-device network I/O is performed.
    """
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    decision_id = (
        prepared["runtime"]["action"]
        ["decision_id"]
    )

    approve_authorization(
        authorization_id,
        execution_environment[
            "authorization_database"
        ],
    )

    simulation_result = run(
        decision_executions
        .simulate_decision_execution(
            authorization_id,
            simulate_payload(),
        )
    )

    assert (
        simulation_result["execution"]
        ["action"]["status"]
        == "completed"
    )

    assert (
        simulation_result["execution"]
        ["simulation"]["status"]
        == "completed"
    )

    assert (
        simulation_result["evidence"]
        ["verified"]
        is True
    )

    assert (
        simulation_result["shadow"]
        ["captured"]
        is True
    )

    shadow_store = ShadowDecisionStore(
        execution_environment[
            "shadow_database"
        ]
    )

    shadow_records = (
        shadow_store.list_recent(
            limit=10
        )
    )

    matching = [
        record
        for record in shadow_records
        if record.decision_id
        == decision_id
    ]

    assert len(matching) == 1

    shadow = matching[0]

    comparison = run(
        autonomous_shadow
        .get_shadow_outcome_comparison(
            shadow.shadow_id
        )
    )

    assert (
        comparison["decision_id"]
        == decision_id
    )

    assert (
        comparison["shadow_id"]
        == shadow.shadow_id
    )

    assert (
        comparison["evidence_verified"]
        is True
    )

    assert (
        comparison["overall_match"]
        is True
    )

    assert (
        comparison["matched_fields"]
        == 6
    )

    assert (
        comparison["mismatched_fields"]
        == 0
    )

    assert (
        comparison["accuracy_percent"]
        == 100.0
    )

    assert (
        comparison["observed_outcome"]
        ["action_status"]
        == "completed"
    )

    assert (
        comparison["observed_outcome"]
        ["simulation_status"]
        == "completed"
    )

    assert (
        comparison["observed_outcome"]
        ["lease_status"]
        == "released"
    )

    safety = comparison["safety"]

    assert safety["read_only"] is True

    assert (
        safety["execution_enabled"]
        is False
    )

    assert (
        safety["execution_authority"]
        is False
    )

    assert (
        safety["network_io_performed"]
        is False
    )

    assert (
        safety["device_command_executed"]
        is False
    )


def test_simulate_pending_authorization_returns_409(
    execution_environment,
) -> None:
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            decision_executions
            .simulate_decision_execution(
                authorization_id,
                simulate_payload(),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "execution_not_allowed"
    )


def test_unknown_runtime_returns_404(
    execution_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            decision_executions
            .simulate_decision_execution(
                "authorization:missing",
                simulate_payload(),
            )
        )

    assert exc.value.status_code == 404


def test_second_simulation_is_blocked(
    execution_environment,
) -> None:
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    approve_authorization(
        authorization_id,
        execution_environment[
            "authorization_database"
        ],
    )

    first = run(
        decision_executions
        .simulate_decision_execution(
            authorization_id,
            simulate_payload(),
        )
    )

    assert (
        first["execution"]["action"]
        ["status"]
        == "completed"
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            decision_executions
            .simulate_decision_execution(
                authorization_id,
                simulate_payload(
                    owner_id=(
                        "worker:second"
                    )
                ),
            )
        )

    assert exc.value.status_code in {
        409,
        503,
    }


def test_response_hides_lease_token(
    execution_environment,
) -> None:
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    approve_authorization(
        authorization_id,
        execution_environment[
            "authorization_database"
        ],
    )

    result = run(
        decision_executions
        .simulate_decision_execution(
            authorization_id,
            simulate_payload(),
        )
    )

    def contains_secret_key(
        value,
    ) -> bool:
        if isinstance(value, dict):
            if "lease_token" in value:
                return True

            return any(
                contains_secret_key(item)
                for item in value.values()
            )

        if isinstance(value, list):
            return any(
                contains_secret_key(item)
                for item in value
            )

        return False

    assert (
        contains_secret_key(result)
        is False
    )

    serialized = json.dumps(
        result,
        sort_keys=True,
    )

    assert '"lease_token":' not in serialized

    assert (
        result["safety"]
        ["lease_token_exposed"]
        is False
    )


def test_failed_simulation_records_failed_action(
    execution_environment,
) -> None:
    prepared = run(
        decision_executions
        .prepare_decision_execution(
            prepare_payload()
        )
    )

    authorization_id = (
        prepared["authorization"]
        ["authorization_id"]
    )

    plan_steps = (
        prepared["runtime"]["plan"]
        ["steps"]
    )

    command_steps = [
        step
        for step in plan_steps
        if step["step_type"] == "command"
    ]

    assert command_steps

    failed_step_id = (
        command_steps[0]["step_id"]
    )

    approve_authorization(
        authorization_id,
        execution_environment[
            "authorization_database"
        ],
    )

    result = run(
        decision_executions
        .simulate_decision_execution(
            authorization_id,
            simulate_payload(
                fail_step_ids=[
                    failed_step_id,
                ]
            ),
        )
    )

    assert (
        result["execution"]["action"]
        ["status"]
        == "failed"
    )

    assert (
        result["execution"]["lease"]
        ["status"]
        == "released"
    )

    assert (
        result["evidence"]["verified"]
        is True
    )


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/decision-executions/"
            "prepare"
        ),
        (
            "/api/v1/decision-executions/"
            "{authorization_id}/simulate"
        ),
    }

    assert expected <= paths
