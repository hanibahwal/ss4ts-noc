from app.services.root_cause_autonomous_orchestrator import (
    orchestrate_root_cause_decision,
)


def test_root_cause_orchestrator_requires_approval():

    result = orchestrate_root_cause_decision(
        {
            "decision_id": "test-1",
            "priority": "HIGH",
            "approval_required": True,
        }
    )


    assert (
        result["execution_mode"]
        ==
        "HUMAN_APPROVAL_REQUIRED"
    )


    assert (
        result["next_stage"]
        ==
        "decision_approval_gateway"
    )
