import inspect
import time
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.main_legacy import app as legacy_app


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_cache_lock = Lock()
_cache_data: dict[str, Any] | None = None
_cache_expires_at = 0.0


def serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    return value


def find_legacy_endpoint(path: str):
    for route in legacy_app.routes:
        if getattr(route, "path", "") == path:
            return route.endpoint

    raise RuntimeError(f"Legacy endpoint was not found: {path}")


async def call_endpoint(endpoint, *args, **kwargs):
    result = endpoint(*args, **kwargs)

    if inspect.isawaitable(result):
        result = await result

    return serialize(result)


def first_number(data: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = data.get(key)

        if isinstance(value, bool):
            continue

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue

    return None


def device_ip(device: dict[str, Any]) -> str | None:
    for key in ("router_ip", "agent_host", "ip", "host", "address"):
        value = device.get(key)

        if value:
            return str(value)

    return None


def device_is_online(device: dict[str, Any]) -> bool:
    status = str(device.get("status", "")).lower()

    return status in {
        "online",
        "up",
        "healthy",
        "connected",
        "active",
    }


async def build_dashboard() -> dict[str, Any]:
    devices_endpoint = find_legacy_endpoint("/api/devices")
    metrics_endpoint = find_legacy_endpoint("/api/metrics/{router_ip}")

    raw_devices = await call_endpoint(devices_endpoint)

    if not isinstance(raw_devices, list):
        raw_devices = []

    devices: list[dict[str, Any]] = []

    cpu_values: list[float] = []
    memory_values: list[float] = []

    total_download_bps = 0.0
    total_upload_bps = 0.0

    for raw_device in raw_devices:
        device = serialize(raw_device)

        if not isinstance(device, dict):
            continue

        router_ip = device_ip(device)
        metrics: dict[str, Any] = {}

        if router_ip:
            try:
                raw_metrics = await call_endpoint(
                    metrics_endpoint,
                    router_ip=router_ip,
                )

                if isinstance(raw_metrics, dict):
                    metrics = raw_metrics
            except HTTPException as exc:
                metrics = {
                    "error": exc.detail,
                    "status_code": exc.status_code,
                }
            except Exception as exc:
                metrics = {
                    "error": str(exc),
                }

        cpu = first_number(
            metrics,
            [
                "cpu",
                "cpu_usage",
                "cpu_percent",
                "cpu_load",
            ],
        )

        memory = first_number(
            metrics,
            [
                "memory",
                "memory_usage",
                "memory_percent",
                "ram_usage",
            ],
        )

        download_bps = first_number(
            metrics,
            [
                "download_bps",
                "rx_bps",
                "in_bps",
                "traffic_in_bps",
            ],
        ) or 0.0

        upload_bps = first_number(
            metrics,
            [
                "upload_bps",
                "tx_bps",
                "out_bps",
                "traffic_out_bps",
            ],
        ) or 0.0

        if cpu is not None:
            cpu_values.append(cpu)

        if memory is not None:
            memory_values.append(memory)

        total_download_bps += download_bps
        total_upload_bps += upload_bps

        devices.append(
            {
                **device,
                "router_ip": router_ip,
                "metrics": metrics,
            }
        )

    total_devices = len(devices)
    online_devices = sum(device_is_online(device) for device in devices)
    offline_devices = total_devices - online_devices

    network_health = (
        round((online_devices / total_devices) * 100, 2)
        if total_devices
        else 0.0
    )

    return {
        "summary": {
            "total_devices": total_devices,
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "network_health_percent": network_health,
            "average_cpu_percent": (
                round(sum(cpu_values) / len(cpu_values), 2)
                if cpu_values
                else 0.0
            ),
            "average_memory_percent": (
                round(sum(memory_values) / len(memory_values), 2)
                if memory_values
                else 0.0
            ),
            "download_bps": round(total_download_bps, 2),
            "upload_bps": round(total_upload_bps, 2),
            "platform_services_online": 4,
            "platform_services_total": 4,
        },
        "devices": devices,
        "generated_at_unix": time.time(),
        "cache_ttl_seconds": settings.snapshot_cache_seconds,
    }


@router.get("")
async def dashboard(refresh: bool = False) -> dict[str, Any]:
    global _cache_data
    global _cache_expires_at

    now = time.monotonic()

    if not refresh and _cache_data is not None and now < _cache_expires_at:
        return {
            **_cache_data,
            "cached": True,
        }

    with _cache_lock:
        now = time.monotonic()

        if not refresh and _cache_data is not None and now < _cache_expires_at:
            return {
                **_cache_data,
                "cached": True,
            }

        snapshot = await build_dashboard()
        snapshot["cached"] = False

        _cache_data = snapshot
        _cache_expires_at = (
            time.monotonic() + settings.snapshot_cache_seconds
        )

        return snapshot
