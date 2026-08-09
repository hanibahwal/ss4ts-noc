from app.services.autonomous_policy_engine import (
    evaluate_autonomous_policy,
)


def test_critical_requires_human_approval():

    result = evaluate_autonomous_policy(
        {
            "decision_id": "test-1",
            "priority": "CRITICAL",
        }
    )

    assert result["approval_required"] is True
    assert result["auto_execute"] is False


def test_low_allows_autonomous_execution():

    result = evaluate_autonomous_policy(
        {
            "decision_id": "test-2",
            "priority": "LOW",
        }
    )

    assert result["auto_execute"] is True
