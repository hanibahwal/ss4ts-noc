from app.services.root_cause_decision_bridge import (
    build_root_cause_decision,
)


def test_root_cause_decision_bridge():

    result = build_root_cause_decision(
        {
            "status": "critical",

            "confidence": 95,

            "primary_root_cause": {

                "code":
                    "HIGH_CPU"

            }

        }
    )


    assert (
        result["decision"]
        ==
        "OPTIMIZE_CPU_LOAD"
    )


    assert (
        result["approval_required"]
        is True
    )


    assert (
        result["confidence_percent"]
        ==
        95
    )
