from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import BaseModel, Field

from app.services.network_discovery_scanner import (
    network_discovery_scanner,
)


router = APIRouter(
    prefix="/discovery",
    tags=["Network Discovery"],
)


class DiscoveryStartRequest(BaseModel):
    network_range: str = Field(
        min_length=3,
        max_length=64,
    )
    name: str | None = Field(
        default=None,
        max_length=120,
    )


@router.post("/start")
def start_discovery(
    payload: DiscoveryStartRequest,
):
    try:
        return network_discovery_scanner.start(
            network_range=payload.network_range,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/jobs/{job_id}")
def discovery_status(
    job_id: str,
):
    try:
        return network_discovery_scanner.get(
            job_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Discovery job not found",
        ) from exc


@router.get("/jobs/{job_id}/devices")
def discovery_devices(
    job_id: str,
):
    try:
        return {
            "job_id": job_id,
            "devices": (
                network_discovery_scanner.results(
                    job_id
                )
            ),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Discovery job not found",
        ) from exc


@router.post("/jobs/{job_id}/cancel")
def cancel_discovery(
    job_id: str,
):
    try:
        return network_discovery_scanner.cancel(
            job_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Discovery job not found",
        ) from exc
