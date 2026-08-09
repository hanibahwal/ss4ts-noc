from app.services.autonomous_learning_loop import (
    evaluate_operation_learning,
)


def test_successful_learning_feedback():

    result = evaluate_operation_learning(
        execution_evidence={
            "verified": True,
            "audit_status": "COMPLETED",
        }
    )

    assert result["learning_status"] == "SUCCESS"
    assert result["feedback_loop"] is True



def test_failed_learning_feedback():

    result = evaluate_operation_learning(
        execution_evidence={
            "verified": False,
            "audit_status": "BLOCKED",
        }
    )

    assert result["learning_status"] == "FAILED"
    assert result["confidence_adjustment"] < 0
