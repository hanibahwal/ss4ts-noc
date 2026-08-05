from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from collections import Counter

from app.services.remediation_audit_history import (
    get_remediation_history,
)


ENGINE_NAME = (
    "SS4TS Executive Remediation Analytics Engine"
)

ENGINE_VERSION = (
    "1.0.0-production"
)


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()



def generate_remediation_analytics() -> dict[str, Any]:

    history = get_remediation_history()


    total = len(history)


    completed = len(
        [
            x for x in history
            if x.get(
                "execution_status"
            ) == "COMPLETED"
        ]
    )


    failed = len(
        [
            x for x in history
            if x.get(
                "execution_status"
            ) == "FAILED"
        ]
    )



    success_rate = 0

    if total:

        success_rate = round(
            (
                completed /
                total
            )
            *
            100,

            2
        )



    actions = Counter(
        x.get(
            "action_type"
        )
        for x in history
    )



    priorities = Counter(
        x.get(
            "priority"
        )
        for x in history
    )



    confidence_values = [

        x.get(
            "confidence",
            0
        )

        for x in history

    ]



    average_confidence = 0

    if confidence_values:

        average_confidence = round(
            sum(confidence_values)
            /
            len(confidence_values),

            2
        )



    return {


        "engine": {

            "name":
                ENGINE_NAME,

            "version":
                ENGINE_VERSION,

        },


        "summary": {


            "total_incidents":
                total,


            "completed":
                completed,


            "failed":
                failed,


            "success_rate":
                success_rate,

        },


        "top_actions":

            [

                {
                    "action":
                        key,

                    "count":
                        value,

                }

                for key, value
                in actions.most_common(10)

            ],



        "risk_analysis": {


            "critical":
                priorities.get(
                    "CRITICAL",
                    0
                ),


            "medium":
                priorities.get(
                    "MEDIUM",
                    0
                ),


            "low":
                priorities.get(
                    "LOW",
                    0
                ),

        },


        "average_confidence":
            average_confidence,


        "recommendation":

            (
                "System stability is improving"
                if success_rate >= 90
                else
                "Additional monitoring required"
            ),



        "generated_at":
            _now(),

    }
