from fastapi import APIRouter

from app.services.executive_notification_bridge import (
    ExecutiveNotificationBridge,
)

from app.services.decision_data_collector import (
    collect_decision_data,
)

from app.services.network_intelligence_collector import (
    collect_network_intelligence,
)


router = APIRouter(
    prefix="/executive",
    tags=["executive"],
)


bridge = ExecutiveNotificationBridge(

    evolution_url="http://mikrotik-whatsapp-api:8080",

    api_key="19d4972f466cfdc5aaa684f388fd68ce12fb1c9cd0634abfc3811ac553a8d271",

    instance="mikrotik-wa-2026",

    target="120363410580738115@g.us",

)


@router.post("/notify")
def executive_notify():

    network_data = collect_network_intelligence(
        router_ip="192.168.45.99",
    )

    interfaces = network_data["traffic"]["interfaces"]

    selected_interface = (
        interfaces[0].get("if_descr")
        if interfaces
        else None
    )

    result = collect_decision_data(
        router_ip=network_data["router_ip"],
        device_name="LTE-5G-ISP-04",
        cpu_usage=network_data["device"]["cpu_usage"],
        memory_usage=network_data["device"]["memory_usage"],
        interfaces=interfaces,
        traffic_history=network_data["traffic"]["history"],
        selected_interface=selected_interface,
    )


    decision = result["decision"]


    risk = decision.get(
        "risk",
        {}
    )


    top_signal = decision.get(
        "top_signal"
    )


    decisions = decision.get(
        "decisions",
        []
    )


    action = (
        decisions[0].get("action")
        if decisions
        else
        "No recommendation"
    )


    confidence = (

        top_signal.get(
            "confidence",
            0
        )

        if top_signal

        else 0

    )


    message = bridge.build_message(

        status=risk.get(
            "level",
            "UNKNOWN"
        ).upper(),


        risk_score=risk.get(
            "score",
            0
        ),


        decision_score=(
            100
            if decisions
            else 0
        ),


        confidence=confidence,


        action=action,

    )


    return bridge.send_whatsapp(message)
