from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.influx import get_influx_client
from app.core.config import settings
from app.services.routeros import get_routeros_client


def collect_interface_traffic(
    router_ip: str,
) -> dict[str, Any]:

    points = []

    try:
        with get_routeros_client(router_ip) as api:

            interfaces = api(
                "/interface/monitor-traffic",
                once="",
            )

            for interface in interfaces:

                name = interface.get("name")

                if not name:
                    continue

                rx = float(
                    interface.get(
                        "rx-bits-per-second",
                        0,
                    )
                    or 0
                )

                tx = float(
                    interface.get(
                        "tx-bits-per-second",
                        0,
                    )
                    or 0
                )


                point = {
                    "measurement": "interface",
                    "tags": {
                        "agent_host": router_ip,
                        "ifDescr": name,
                    },
                    "fields": {
                        "ifHCInOctets": rx / 8,
                        "ifHCOutOctets": tx / 8,
                    },
                    "time": datetime.now(
                        timezone.utc
                    ),
                }

                points.append(point)


        if points:

            with get_influx_client() as client:

                client.write_api().write(
                    bucket=settings.influx_bucket,
                    org=settings.influx_org,
                    record=points,
                )


        return {
            "router_ip": router_ip,
            "interfaces": len(points),
            "status": "ok",
        }


    except Exception as exc:

        return {
            "router_ip": router_ip,
            "status": "error",
            "error": str(exc),
        }
