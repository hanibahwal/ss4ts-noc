# =====================================================
# H23.4.5.5.12.X.4.7.3
# SS4TS Fleet Health API Gateway
# =====================================================


from fastapi import APIRouter


from app.services.fleet_health_intelligence import (
    generate_fleet_health_report,
)



router = APIRouter(
    prefix="/fleet",
    tags=[
        "fleet-health"
    ]
)



@router.get(
    "/health"
)
def fleet_health():

    return generate_fleet_health_report()
