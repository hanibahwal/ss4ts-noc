from app.services.execution_simulation_engine import (
    simulate_execution,
)


def test_critical_change_blocked():

    result = simulate_execution(
        {
            "priority": "CRITICAL",
            "action": "CHANGE_ROUTING",
        }
    )

    assert result["safe_to_execute"] is False
    assert result["rollback_required"] is True



def test_low_risk_simulation_passed():

    result = simulate_execution(
        {
            "priority": "LOW",
            "action": "SAFE_OPTIMIZATION",
        }
    )

    assert result["safe_to_execute"] is True
    assert result["rollback_required"] is False
