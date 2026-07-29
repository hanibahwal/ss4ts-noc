from fastapi import APIRouter

from app.services.influx import get_influx_client


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict:
    influx_status = "offline"

    try:
        with get_influx_client() as client:
            influx_status = (
                "online"
                if client.health().status == "pass"
                else "degraded"
            )
    except Exception:
        influx_status = "offline"

    return {
        "status": "healthy" if influx_status == "online" else "degraded",
        "service": "ss4ts-api",
        "influxdb": influx_status,
    }
