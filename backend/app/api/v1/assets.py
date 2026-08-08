from fastapi import APIRouter

from app.services.asset_store import asset_store
from app.services.asset_intelligence_service import (
    asset_intelligence_service
)


router = APIRouter(
    prefix="/api/v1/assets",
    tags=["Asset Inventory"]
)


@router.get("/intelligence")
def intelligence():

    rows = asset_store.list_all()

    results = []

    for row in rows:

        asset = {

            "asset_id": row[0],
            "ip_address": row[1],
            "vendor": row[2],
            "model": row[3],
            "identity": row[4],
            "platform": row[5],
            "version": row[6],
            "architecture": row[7],
            "cpu": row[8],
            "cpu_count": row[9],
            "memory_usage": row[10],
            "uptime": row[11],
            "device_type": row[12],
            "confidence": row[13],

        }


        results.append(
            asset_intelligence_service.analyze(
                asset
            )
        )


    return {

        "total_assets": len(results),

        "healthy":
            len(
                [
                    x for x in results
                    if x["health_status"] == "GOOD"
                ]
            ),

        "warning":
            len(
                [
                    x for x in results
                    if x["health_status"] == "WARNING"
                ]
            ),

        "critical":
            len(
                [
                    x for x in results
                    if x["health_status"] == "CRITICAL"
                ]
            ),

        "assets": results
    }



@router.get("")
def list_assets():

    rows = asset_store.list_all()

    assets=[]

    for row in rows:

        assets.append({

            "asset_id":row[0],
            "ip_address":row[1],
            "vendor":row[2],
            "model":row[3],
            "identity":row[4],
            "platform":row[5],
            "version":row[6],
            "architecture":row[7],
            "cpu":row[8],
            "memory_usage":row[10],
            "uptime":row[11],
            "confidence":row[13]

        })


    return {

        "total":len(assets),
        "assets":assets

    }



@router.get("/{ip_address}")
def get_asset(ip_address:str):

    rows=asset_store.list_all()

    for row in rows:

        if row[1]==ip_address:

            return {

            "asset_id":row[0],
            "ip_address":row[1],
            "vendor":row[2],
            "model":row[3],
            "identity":row[4],
            "version":row[6],
            "memory_usage":row[10],
            "confidence":row[13]

            }


    return {

        "error":"Asset not found",
        "ip_address":ip_address

    }
