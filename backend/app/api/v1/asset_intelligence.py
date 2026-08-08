from fastapi import APIRouter

from app.services.asset_store import asset_store

from app.services.asset_intelligence_service import (
    asset_intelligence_service
)


router = APIRouter(
    prefix="/api/v1/assets",
    tags=["Asset Intelligence"]
)


@router.get("/intelligence")
def asset_intelligence():

    rows = asset_store.list_all()


    assets = []

    total_score = 0

    legacy = 0

    high_memory = 0


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
            "status": row[14],

        }


        intelligence = (
            asset_intelligence_service.analyze(
                asset
            )
        )


        assets.append(
            intelligence
        )


        total_score += (
            intelligence["health_score"]
        )


        if "Legacy RouterOS version" in intelligence["risks"]:

            legacy += 1


        if "High memory utilization" in intelligence["risks"]:

            high_memory += 1



    average = 0

    if assets:

        average = round(
            total_score / len(assets),
            2
        )


    return {

        "total_assets": len(assets),

        "average_health_score":
            average,

        "legacy_devices":
            legacy,

        "high_memory_devices":
            high_memory,

        "executive_summary":
            (
            f"{len(assets)} assets analyzed. "
            f"{legacy} legacy RouterOS devices detected."
            ),

        "assets":
            assets

    }
