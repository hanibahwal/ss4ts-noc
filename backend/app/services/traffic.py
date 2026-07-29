from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.core.config import settings
from app.services.influx import get_influx_client


EXCLUDED_INTERFACES = {
    "lo",
    "loopback",
}


def _escape_flux(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def get_interface_rates(
    router_ip: str,
    range_minutes: int = 5,
) -> dict[str, Any]:
    safe_ip = _escape_flux(router_ip)
    safe_bucket = _escape_flux(settings.influx_bucket)

    flux = f'''
from(bucket: "{safe_bucket}")
  |> range(start: -{range_minutes}m)
  |> filter(fn: (r) =>
      r._measurement == "interface" and
      r.agent_host == "{safe_ip}" and
      (
        r._field == "ifHCInOctets" or
        r._field == "ifHCOutOctets"
      )
  )
  |> derivative(unit: 1s, nonNegative: true)
  |> map(fn: (r) => ({{r with _value: float(v: r._value) * 8.0}}))
  |> last()
  |> keep(columns: [
      "_time",
      "_field",
      "_value",
      "agent_host",
      "ifDescr",
      "ifIndex"
  ])
'''

    rates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "if_descr": "",
            "if_index": None,
            "rx_bps": 0.0,
            "tx_bps": 0.0,
            "total_bps": 0.0,
            "time": None,
        }
    )

    with get_influx_client() as client:
        tables = client.query_api().query(
            query=flux,
            org=settings.influx_org,
        )

    for table in tables:
        for record in table.records:
            values = record.values

            if_descr = str(values.get("ifDescr") or "unknown")
            field = str(record.get_field())
            value = float(record.get_value() or 0.0)

            interface = rates[if_descr]
            interface["if_descr"] = if_descr
            interface["if_index"] = values.get("ifIndex")
            interface["time"] = (
                record.get_time().isoformat()
                if record.get_time()
                else None
            )

            if field == "ifHCInOctets":
                interface["rx_bps"] = max(value, 0.0)
            elif field == "ifHCOutOctets":
                interface["tx_bps"] = max(value, 0.0)

    interfaces: list[dict[str, Any]] = []

    for interface in rates.values():
        interface["total_bps"] = round(
            interface["rx_bps"] + interface["tx_bps"],
            2,
        )
        interface["rx_bps"] = round(interface["rx_bps"], 2)
        interface["tx_bps"] = round(interface["tx_bps"], 2)
        interfaces.append(interface)

    interfaces.sort(
        key=lambda item: item["total_bps"],
        reverse=True,
    )

    eligible = [
        item
        for item in interfaces
        if item["if_descr"].lower() not in EXCLUDED_INTERFACES
        and item["total_bps"] > 0
    ]

    selected = eligible[0] if eligible else None

    return {
        "router_ip": router_ip,
        "selected_interface": (
            selected["if_descr"]
            if selected
            else None
        ),
        "rx_bps": selected["rx_bps"] if selected else 0.0,
        "tx_bps": selected["tx_bps"] if selected else 0.0,
        "total_bps": selected["total_bps"] if selected else 0.0,
        "interfaces": interfaces,
    }
