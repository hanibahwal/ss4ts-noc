from fastapi import APIRouter, HTTPException
from typing import Any

from app.services.fleet_device_registry import (
    register_device,
    get_device,
    list_devices,
)


router = APIRouter(
    prefix="/fleet",
    tags=["fleet"],
)



@router.post("/device/register")
def create_device(
    payload: dict[str, Any]
):

    device_id = register_device(
        hostname=payload.get(
            "hostname",
            "UNKNOWN"
        ),

        router_ip=payload["router_ip"],

        site=payload.get(
            "site",
            "UNKNOWN"
        ),

        model=payload.get(
            "model",
            "UNKNOWN"
        ),

        role=payload.get(
            "role",
            "UNKNOWN"
        ),

        status=payload.get(
            "status",
            "UNKNOWN"
        ),

        health_score=payload.get(
            "health_score",
            0
        ),
    )


    return {

        "success": True,

        "device_id": device_id,

    }





@router.get("/devices")
def devices():

    data = list_devices()


    return {

        "engine":
        {
            "name":
            "SS4TS Enterprise Fleet Registry API",

            "version":
            "1.0.0",
        },


        "fleet_size":
            len(data),


        "devices":
            data,

    }





@router.get("/device/{router_ip}")
def device(
    router_ip: str
):

    result = get_device(
        router_ip
    )


    if not result:

        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )


    return result
