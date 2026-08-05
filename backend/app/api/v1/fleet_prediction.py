from fastapi import APIRouter

from app.services.fleet_risk_prediction import (
    generate_fleet_prediction,
)


router = APIRouter(
    prefix="/fleet",
    tags=["fleet"]
)



@router.get("/prediction")
def fleet_prediction():

    return generate_fleet_prediction()
