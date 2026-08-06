from __future__ import annotations

import asyncio

from fastapi import HTTPException

from app.api.v1 import (
    autonomous_proposal_binding,
)
from app.api.v1.router import api_router
from tests.test_autonomous_proposal_binding import (
    make_bound_objects,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


def test_router_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert any(
        path.endswith(
            "/autonomous-proposals/"
            "validate-binding"
        )
        for path in paths
    )


def test_valid_binding_endpoint() -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    result = run(
        autonomous_proposal_binding
        .validate_autonomous_proposal_binding(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result["binding_valid"] is True
    assert result["binding_errors"] == []
    assert result["can_execute"] is False


def test_endpoint_returns_all_checks() -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    result = run(
        autonomous_proposal_binding
        .validate_autonomous_proposal_binding(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result["checks"] == {
        "decision_consistent": True,
        "plan_consistent": True,
        "target_consistent": True,
        "operation_consistent": True,
        "confidence_consistent": True,
        "risk_consistent": True,
        "policy_review_allowed": True,
        "proposal_not_expired": True,
        "human_approval_required": True,
        "dry_run_only": True,
    }


def test_endpoint_has_no_execution_authority() -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    result = run(
        autonomous_proposal_binding
        .validate_autonomous_proposal_binding(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result["can_execute"] is False

    assert result["safety"] == {
        "binding_validation_only": True,
        "execution_authority": False,
        "authorization_created": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
        "controlled_execution_required": True,
    }


def test_mismatched_objects_are_rejected() -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.decision_id = (
        "decision:different"
    )

    proposal.plan_id = (
        "plan:different"
    )

    proposal.target_node_id = (
        "device:different"
    )

    result = run(
        autonomous_proposal_binding
        .validate_autonomous_proposal_binding(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result["binding_valid"] is False

    assert (
        "Decision identifiers do not match"
        in result["binding_errors"]
    )

    assert (
        "Execution plan identifier "
        "does not match"
        in result["binding_errors"]
    )

    assert (
        "Proposal target does not match "
        "the action and execution plan"
        in result["binding_errors"]
    )

    assert result["can_execute"] is False


def test_non_dry_run_plan_is_rejected() -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    plan.dry_run_only = False

    result = run(
        autonomous_proposal_binding
        .validate_autonomous_proposal_binding(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result["binding_valid"] is False
    assert result["checks"]["dry_run_only"] is False

    assert (
        "Execution plan must be dry-run-only"
        in result["binding_errors"]
    )

    assert result["can_execute"] is False


def test_invalid_type_returns_400() -> None:
    _, action, plan = (
        make_bound_objects()
    )

    try:
        run(
            autonomous_proposal_binding
            .validate_autonomous_proposal_binding(
                proposal={},
                action=action,
                plan=plan,
            )
        )

    except HTTPException as exc:
        assert exc.status_code == 400
        assert (
            "AutonomousOperationProposal"
            in str(exc.detail)
        )

    else:
        raise AssertionError(
            "Expected HTTPException"
        )
