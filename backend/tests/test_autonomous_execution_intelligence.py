from app.services.autonomous_execution_intelligence import (
    evaluate_execution_plan,
)


def test_critical_requires_approval():

    result = evaluate_execution_plan(
        {
            "priority": "CRITICAL"
        }
    )

    assert result["approval_required"] is True
    assert result["rollback_required"] is True



def test_low_risk_allows_execution():

    result = evaluate_execution_plan(
        {
            "priority": "LOW"
        }
    )

    assert result["execution_allowed"] is True
    assert result["approval_required"] is False
