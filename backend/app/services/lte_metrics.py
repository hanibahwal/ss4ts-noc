from __future__ import annotations

import os
from typing import Any

import routeros_api


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _bool_from_routeros(value: Any) -> bool | None:
    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized in {"true", "yes", "1"}:
        return True

    if normalized in {"false", "no", "0"}:
        return False

    return None


def _required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required LTE environment variable is missing: {name}"
        )

    return value


def get_lte_metrics() -> dict[str, Any]:
    """
    Collect current LTE modem metrics through RouterOS API.

    Environment variables:
    - LTE_ROUTER_IP
    - LTE_INTERFACE
    - LTE_API_USERNAME
    - LTE_API_PASSWORD
    - LTE_API_PORT
    """

    host = _required_env("LTE_ROUTER_IP")
    username = _required_env("LTE_API_USERNAME")
    password = _required_env("LTE_API_PASSWORD")

    interface_name = os.getenv(
        "LTE_INTERFACE",
        "lte1",
    )

    port = int(
        os.getenv(
            "LTE_API_PORT",
            "8728",
        )
    )

    pool = routeros_api.RouterOsApiPool(
        host=host,
        username=username,
        password=password,
        port=port,
        plaintext_login=True,
        use_ssl=False,
    )

    try:
        api = pool.get_api()

        identity_rows = api.get_resource(
            "/system/identity"
        ).get()

        lte_rows = api.get_resource(
            "/interface/lte"
        ).get()

        matching_interfaces = [
            row
            for row in lte_rows
            if row.get("name") == interface_name
        ]

        if not matching_interfaces:
            raise RuntimeError(
                f"LTE interface not found: {interface_name}"
            )

        interface_row = matching_interfaces[0]

        monitor_rows = api.get_resource(
            "/interface/lte"
        ).call(
            "monitor",
            {
                "numbers": interface_name,
                "once": "",
            },
        )

        if not monitor_rows:
            raise RuntimeError(
                f"No LTE monitor data returned for {interface_name}"
            )

        monitor = monitor_rows[0]

        identity = None

        if identity_rows:
            identity = identity_rows[0].get("name")

        status = monitor.get("status")
        running = (
            str(status).strip().lower() == "running"
        )

        return {
            "available": True,
            "running": running,
            "status": status,
            "router_identity": identity,
            "router_ip": host,
            "interface": interface_name,
            "interface_running": _bool_from_routeros(
                interface_row.get("running")
            ),
            "interface_disabled": _bool_from_routeros(
                interface_row.get("disabled")
            ),
            "model": monitor.get("model"),
            "revision": monitor.get("revision"),
            "operator": monitor.get(
                "current-operator"
            ),
            "data_class": monitor.get(
                "data-class"
            ),
            "session_uptime": monitor.get(
                "session-uptime"
            ),
            "cell_id": monitor.get(
                "current-cellid"
            ),
            "enb_id": monitor.get("enb-id"),
            "sector_id": monitor.get(
                "sector-id"
            ),
            "phy_cell_id": monitor.get(
                "phy-cellid"
            ),
            "primary_band": monitor.get(
                "primary-band"
            ),
            "ca_band": monitor.get(
                "ca-band"
            ),
            "ul_ca_band": monitor.get(
                "ul-ca-band"
            ),
            "dl_modulation": monitor.get(
                "dl-modulation"
            ),
            "cqi": _int_or_none(
                monitor.get("cqi")
            ),
            "ri": _int_or_none(
                monitor.get("ri")
            ),
            "mcs": _int_or_none(
                monitor.get("mcs")
            ),
            "rssi_dbm": _int_or_none(
                monitor.get("rssi")
            ),
            "rsrp_dbm": _int_or_none(
                monitor.get("rsrp")
            ),
            "rsrq_db": _int_or_none(
                monitor.get("rsrq")
            ),
            "sinr_db": _int_or_none(
                monitor.get("sinr")
            ),
            "source": "routeros_api_lte_monitor",
        }

    finally:
        pool.disconnect()
