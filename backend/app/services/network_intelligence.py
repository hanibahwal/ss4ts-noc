from __future__ import annotations

from typing import Any


from app.services.prediction_memory_store import (
    save_prediction_memory,
)


from app.services.prediction_learning import (
    analyze_prediction_history,
)


from app.services.pattern_recognition import (
    analyze_prediction_patterns,
)


from app.services.failure_forecasting import (
    forecast_failure,
)


from app.services.executive_decision_engine import (
    generate_executive_decision,
)


from app.services.response_action_planner import (
    generate_response_plan,
)


from app.services.autonomous_noc_dashboard import (
    build_autonomous_dashboard,
)


from app.services.network_intelligence_analyzer import (
    analyze_network_intelligence,
)


from app.services.network_intelligence_collector import (
    collect_network_intelligence,
)


from app.services.prediction_engine import (
    generate_prediction,
)


SERVICE_NAME = (
    "SS4TS Network Intelligence Service"
)


SERVICE_VERSION = (
    "1.7.0-autonomous-ai-noc"
)



def get_network_intelligence(
    *,
    router_ip: str,
    include_history: bool = True,
    history_minutes: int = 15,
    history_window_seconds: int = 10,
) -> dict[str, Any]:
    """
    Unified Network Intelligence Service.

    Includes:

    - Live Collector
    - Health Analysis
    - AI Prediction Engine
    - AI Prediction Memory
    - Learning Loop
    - Pattern Recognition Engine
    - Failure Forecasting Engine
    - Executive Decision Engine
    - Response Action Planner
    - Autonomous AI NOC Dashboard


    H23.4.5.5.12.X.4.6
    """



    collector = collect_network_intelligence(
        router_ip=router_ip,
        include_history=include_history,
        history_minutes=history_minutes,
        history_window_seconds=history_window_seconds,
    )



    analysis = analyze_network_intelligence(
        collector
    )



    prediction = generate_prediction(
        device=collector.get(
            "device",
            {},
        ),

        traffic=collector.get(
            "traffic",
            {},
        ),

        lte=collector.get(
            "lte",
            {},
        ),

        ping=collector.get(
            "ping",
            {},
        ),
    )



    save_prediction_memory(
        router_ip=router_ip,
        prediction=prediction,
    )



    learning = analyze_prediction_history(
        router_ip=router_ip,
    )



    pattern_analysis = analyze_prediction_patterns(
        router_ip=router_ip,
    )



    failure_forecast = forecast_failure(
        pattern_analysis=pattern_analysis,
        prediction=prediction,
    )



    executive_decision = (
        generate_executive_decision(
            prediction=prediction,
            pattern_analysis=pattern_analysis,
            failure_forecast=failure_forecast,
        )
    )



    response_plan = (
        generate_response_plan(
            executive_decision=executive_decision,
            router_ip=router_ip,
        )
    )



    autonomous_dashboard = (
        build_autonomous_dashboard(
            router_ip=router_ip,

            intelligence={

                "health_score":
                    analysis.get(
                        "overall_health_score"
                    ),


                "status":
                    analysis.get(
                        "overall_health"
                    ),


                "prediction":
                    prediction,


                "failure_forecast":
                    failure_forecast,


                "executive_decision":
                    executive_decision,


                "response_plan":
                    response_plan,

            },
        )
    )



    return {

        "router_ip": collector.get(
            "router_ip"
        ),



        "generated_at": collector.get(
            "generated_at"
        ),



        "status": analysis.get(
            "overall_health"
        ),



        "health_score": analysis.get(
            "overall_health_score"
        ),



        "confidence_percent": analysis.get(
            "confidence_percent"
        ),



        "collector": collector,



        "analysis": analysis,



        "prediction": prediction,



        "learning": learning,



        "pattern_analysis": pattern_analysis,



        "failure_forecast": failure_forecast,



        "executive_decision": executive_decision,



        "response_plan": response_plan,



        "autonomous_dashboard":
            autonomous_dashboard,



        "service": {

            "name": SERVICE_NAME,


            "version": SERVICE_VERSION,

        },

    }
