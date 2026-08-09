from app.services.autonomous_execution_runtime import (
    execute_autonomous_action,
)


def test_blocked_execution():

    result = execute_autonomous_action(
        decision={
            "decision_id": "d1",
            "action": "CHANGE_ROUTE",
        },
        simulation={
            "safe_to_execute": False,
        },
    )

    assert result["executed"] is False
    assert result["status"] == "BLOCKED"



def test_successful_execution():

    result = execute_autonomous_action(
        decision={
            "decision_id": "d2",
            "action": "SAFE_OPTIMIZATION",
        },
        simulation={
            "safe_to_execute": True,
            "simulation_status": "PASSED",
            "confidence": 90,
        },
    )

    assert result["executed"] is True
    assert result["status"] == "EXECUTED"
