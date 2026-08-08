from __future__ import annotations

import os
from typing import Any

import httpx


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_cpu_usage(value: Any) -> float | None:
    """
    Protect Executive AI from false CPU alerts.

    RouterOS REST API may return unstable CPU values.
    Normalize the value before sending it to analytics.
    """
    cpu = _to_float(value)

    if cpu is None:
        return None

    if cpu < 0:
        return None

    if cpu > 100:
        return 100.0

    return round(cpu, 2)


def _first_item(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        if not value:
            return {}

        item = value[0]
        return item if isinstance(item, dict) else {}

    return value if isinstance(value, dict) else {}


class RouterOSClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = f"https://{host}/rest"
        self.auth = (username, password)
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def get(self, resource: str) -> Any:
        with httpx.Client(
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=self.timeout,
        ) as client:
            response = client.get(
                f"{self.base_url}/{resource.lstrip('/')}"
            )
            response.raise_for_status()
            return response.json()


def get_routeros_client(host: str) -> RouterOSClient:
    username = os.getenv("MIKROTIK_API_USERNAME", "")
    password = os.getenv("MIKROTIK_API_PASSWORD", "")

    if not username or not password:
        raise RuntimeError(
            "MikroTik API credentials are not configured"
        )

    verify_ssl = os.getenv(
        "MIKROTIK_API_VERIFY_SSL",
        "false",
    ).lower() in {"1", "true", "yes"}

    timeout = float(
        os.getenv("MIKROTIK_API_TIMEOUT", "10")
    )

    return RouterOSClient(
        host=host,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        timeout=timeout,
    )


def get_system_snapshot(host: str) -> dict[str, Any]:
    client = get_routeros_client(host)

    resource = _first_item(
        client.get("system/resource")
    )

    identity = _first_item(
        client.get("system/identity")
    )

    health_rows: list[dict[str, Any]] = []

    try:
        raw_health = client.get("system/health")

        if isinstance(raw_health, list):
            health_rows = [
                row
                for row in raw_health
                if isinstance(row, dict)
            ]

    except httpx.HTTPError:
        health_rows = []

    health = {
        str(row.get("name")): row.get("value")
        for row in health_rows
        if row.get("name")
    }

    total_memory = _to_float(
        resource.get("total-memory")
    )

    free_memory = _to_float(
        resource.get("free-memory")
    )

    memory_usage = None

    if (
        total_memory is not None
        and total_memory > 0
        and free_memory is not None
    ):
        memory_usage = round(
            ((total_memory - free_memory) / total_memory) * 100,
            2,
        )

    temperature = None

    for key in (
        "temperature",
        "cpu-temperature",
        "board-temperature",
    ):
        value = _to_float(health.get(key))

        if value is not None:
            temperature = value
            break

    return {
        "identity": identity.get("name"),
        "board_name": resource.get("board-name"),
        "platform": resource.get("platform"),
        "architecture": resource.get("architecture-name"),
        "version": resource.get("version"),
        "cpu": resource.get("cpu"),
        "cpu_count": _to_float(resource.get("cpu-count")),
        "cpu_frequency_mhz": _to_float(
            resource.get("cpu-frequency")
        ),
        "cpu_usage": _safe_cpu_usage(
            resource.get("cpu-load")
        ),
        "cpu_source": "RouterOS system/resource cpu-load",
        "total_memory_bytes": total_memory,
        "free_memory_bytes": free_memory,
        "memory_usage": memory_usage,
        "uptime": resource.get("uptime"),
        "temperature": temperature,
        "health": health,
    }
