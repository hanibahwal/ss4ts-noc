from app.services.autonomous_evidence_audit import (
    create_execution_evidence,
)


def test_execution_evidence_completed():

    result = create_execution_evidence(
        execution_result={
            "execution_id": "exec-1",
            "executed": True,
            "status": "EXECUTED",
        },
        decision={
            "decision_id": "dec-1",
            "action": "SAFE_OPTIMIZATION",
        },
    )

    assert result["verified"] is True
    assert result["audit_status"] == "COMPLETED"



def test_blocked_execution_audit():

    result = create_execution_evidence(
        execution_result={
            "execution_id": "exec-2",
            "executed": False,
            "status": "BLOCKED",
        },
        decision={
            "decision_id": "dec-2",
        },
    )

    assert result["verified"] is False
    assert result["audit_status"] == "BLOCKED"
