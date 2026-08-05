"""
Executive Prediction API

H23.4.5.5.12.X.4.2.3

Provides AI based network predictions.
"""

from fastapi import APIRouter

from app.services.trend_analyzer import analyze_device


router = APIRouter(
    prefix="/executive",
    tags=["executive-prediction"],
)


@router.get("/{router_ip}/prediction")
def executive_prediction(
    router_ip: str
):

    result = analyze_device(
        router_ip
    )

    return {
        "module":
            "Predictive Network Intelligence",

        "device":
            router_ip,

        "prediction":
            result
    }
