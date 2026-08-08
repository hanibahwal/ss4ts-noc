from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.routeros import (
    get_system_snapshot,
)


class RouterOSLiveMetrics:
    """
    SS4TS-NOC H30.4
    Real RouterOS Live Metrics Collector

    Source:
    RouterOS REST API

    Metrics:
    - Identity
    - Board
    - Version
    - CPU
    - Memory
    - Uptime
    - Architecture
    """


    def collect(
        self,
        router_ip: str,
    ) -> dict[str, Any]:

        result = {

            "router_ip": router_ip,

            "collected_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "available": False,

            "identity": None,

            "board_name": None,

            "version": None,

            "architecture": None,

            "cpu_usage_percent": None,

            "memory_usage_percent": None,

            "uptime": None,

            "interfaces": [],

            "traffic": {

                "rx_bps": 0,

                "tx_bps": 0,

                "total_bps": 0,

            },

            "source":
                "RouterOS REST API",

        }


        try:

            snapshot = (
                get_system_snapshot(
                    router_ip
                )
            )


            result["available"] = True


            result["identity"] = (
                snapshot.get(
                    "identity"
                )
            )


            result["board_name"] = (
                snapshot.get(
                    "board_name"
                )
            )


            result["version"] = (
                snapshot.get(
                    "version"
                )
            )


            result["architecture"] = (
                snapshot.get(
                    "architecture"
                )
            )


            result["cpu_usage_percent"] = (
                snapshot.get(
                    "cpu_usage"
                )
            )


            result["memory_usage_percent"] = (
                snapshot.get(
                    "memory_usage"
                )
            )


            result["uptime"] = (
                snapshot.get(
                    "uptime"
                )
            )


            result["health"] = (
                snapshot.get(
                    "health",
                    {}
                )
            )


        except Exception as exc:

            result["error"] = str(exc)


        return result



routeros_live_metrics = (
    RouterOSLiveMetrics()
)
