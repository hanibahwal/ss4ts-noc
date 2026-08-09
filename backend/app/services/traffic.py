from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.services.influx import get_influx_client


EXCLUDED_INTERFACES = {
    "lo",
    "loopback",
}


def _escape_flux(value: str) -> str:
    """Escape user-controlled values before placing them in Flux queries."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _validate_range_minutes(range_minutes: int) -> int:
    """Restrict history ranges to a safe operational limit."""
    return max(1, min(int(range_minutes), 1440))


def _validate_window_seconds(window_seconds: int) -> int:
    """Restrict aggregation windows to a reasonable range."""
    return max(1, min(int(window_seconds), 300))


def get_interface_rates(
    router_ip: str,
    range_minutes: int = 5,
) -> dict[str, Any]:
    """
    Return the latest RX/TX rate for every interface.

    Values are calculated from SNMP high-capacity octet counters
    and returned in bits per second.
    """
    safe_ip = _escape_flux(router_ip)
    safe_bucket = _escape_flux(settings.influx_bucket)
    range_minutes = _validate_range_minutes(range_minutes)

    flux = f'''
from(bucket: "{safe_bucket}")
  |> range(start: -{range_minutes}m)
  |> filter(fn: (r) =>
      r._measurement == "interface" and
      r.agent_host == "{safe_ip}" and
      (
        r._field == "ifHCInOctets" or
        r._field == "ifHCOutOctets" or
        r._field == "ifInOctets" or
        r._field == "ifOutOctets"
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

            if field in ("ifHCInOctets", "ifInOctets"):
                interface["rx_bps"] = max(value, 0.0)
            elif field in ("ifHCOutOctets", "ifOutOctets"):
                interface["tx_bps"] = max(value, 0.0)

    interfaces: list[dict[str, Any]] = []

    for interface in rates.values():
        interface["rx_bps"] = round(interface["rx_bps"], 2)
        interface["tx_bps"] = round(interface["tx_bps"], 2)
        interface["total_bps"] = round(
            interface["rx_bps"] + interface["tx_bps"],
            2,
        )
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
            selected["if_descr"] if selected else None
        ),
        "rx_bps": selected["rx_bps"] if selected else 0.0,
        "tx_bps": selected["tx_bps"] if selected else 0.0,
        "total_bps": selected["total_bps"] if selected else 0.0,
        "interfaces": interfaces,
    }


def get_interface_history(
    router_ip: str,
    interface_name: str | None = None,
    range_minutes: int = 15,
    window_seconds: int = 10,
) -> dict[str, Any]:
    """
    Return time-series RX/TX traffic for one interface.

    When interface_name is not provided, the most active interface
    is selected using the current interface-rate query.
    """
    range_minutes = _validate_range_minutes(range_minutes)
    window_seconds = _validate_window_seconds(window_seconds)

    if not interface_name:
        current = get_interface_rates(
            router_ip=router_ip,
            range_minutes=min(range_minutes, 5),
        )
        interface_name = current.get("selected_interface")

    if not interface_name:
        return {
            "router_ip": router_ip,
            "interface": None,
            "range_minutes": range_minutes,
            "window_seconds": window_seconds,
            "points": [],
        }

    safe_ip = _escape_flux(router_ip)
    safe_interface = _escape_flux(interface_name)
    safe_bucket = _escape_flux(settings.influx_bucket)

    flux = f'''
from(bucket: "{safe_bucket}")
  |> range(start: -{range_minutes}m)
  |> filter(fn: (r) =>
      r._measurement == "interface" and
      r.agent_host == "{safe_ip}" and
      r.ifDescr == "{safe_interface}" and
      (
        r._field == "ifHCInOctets" or
        r._field == "ifHCOutOctets" or
        r._field == "ifInOctets" or
        r._field == "ifOutOctets"
      )
  )
  |> derivative(unit: 1s, nonNegative: true)
  |> map(fn: (r) => ({{r with _value: float(v: r._value) * 8.0}}))
  |> aggregateWindow(
      every: {window_seconds}s,
      fn: mean,
      createEmpty: false
  )
  |> keep(columns: [
      "_time",
      "_field",
      "_value",
      "ifDescr"
  ])
  |> sort(columns: ["_time"])
'''

    points_by_time: dict[str, dict[str, Any]] = {}

    with get_influx_client() as client:
        tables = client.query_api().query(
            query=flux,
            org=settings.influx_org,
        )

    for table in tables:
        for record in table.records:
            record_time: datetime | None = record.get_time()

            if record_time is None:
                continue

            time_key = record_time.isoformat()
            field = str(record.get_field())
            value = max(float(record.get_value() or 0.0), 0.0)

            point = points_by_time.setdefault(
                time_key,
                {
                    "time": time_key,
                    "rx_bps": 0.0,
                    "tx_bps": 0.0,
                    "total_bps": 0.0,
                },
            )

            if field in ("ifHCInOctets", "ifInOctets"):
                point["rx_bps"] = round(value, 2)
            elif field in ("ifHCOutOctets", "ifOutOctets"):
                point["tx_bps"] = round(value, 2)

    points = list(points_by_time.values())

    for point in points:
        point["total_bps"] = round(
            point["rx_bps"] + point["tx_bps"],
            2,
        )

    points.sort(key=lambda item: item["time"])

    return {
        "router_ip": router_ip,
        "interface": interface_name,
        "range_minutes": range_minutes,
        "window_seconds": window_seconds,
        "points": points,
    }




def _status_name(value: Any) -> str:
    """
    Convert IF-MIB status values to readable names.

    1 = up
    2 = down
    3 = testing
    4 = unknown
    5 = dormant
    6 = notPresent
    7 = lowerLayerDown
    """
    status_map = {
        1: "up",
        2: "down",
        3: "testing",
        4: "unknown",
        5: "dormant",
        6: "not_present",
        7: "lower_layer_down",
    }

    try:
        return status_map.get(int(value), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def _interface_type_name(value: Any) -> str:
    """Return a friendly name for common IF-MIB interface types."""
    type_map = {
        1: "other",
        6: "ethernet",
        23: "ppp",
        24: "software_loopback",
        53: "virtual",
        71: "wifi",
        131: "tunnel",
        135: "vlan",
        209: "bridge",
    }

    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return "unknown"

    return type_map.get(
        numeric_value,
        f"type_{numeric_value}",
    )


def get_interfaces_snapshot(
    router_ip: str,
    range_minutes: int = 15,
) -> dict[str, Any]:
    """
    Return operational information and current traffic
    for all interfaces belonging to one monitored device.
    """
    safe_ip = _escape_flux(router_ip)
    safe_bucket = _escape_flux(settings.influx_bucket)
    range_minutes = _validate_range_minutes(range_minutes)

    fields = [
        "ifAdminStatus",
        "ifOperStatus",
        "ifSpeed",
        "ifMtu",
        "ifType",
        "ifInErrors",
        "ifOutErrors",
    ]

    field_filter = " or ".join(
        f'r._field == "{field_name}"'
        for field_name in fields
    )

    flux = f'''
from(bucket: "{safe_bucket}")
  |> range(start: -{range_minutes}m)
  |> filter(fn: (r) =>
      r._measurement == "interface" and
      r.agent_host == "{safe_ip}" and
      ({field_filter})
  )
  |> group(columns: [
      "ifDescr",
      "ifIndex",
      "_field"
  ])
  |> last()
  |> group(columns: [
      "ifDescr",
      "ifIndex"
  ])
  |> pivot(
      rowKey: ["ifDescr", "ifIndex"],
      columnKey: ["_field"],
      valueColumn: "_value"
  )
  |> keep(columns: [
      "ifDescr",
      "ifIndex",
      "ifAdminStatus",
      "ifOperStatus",
      "ifSpeed",
      "ifMtu",
      "ifType",
      "ifInErrors",
      "ifOutErrors",
      "_time"
  ])
'''

    with get_influx_client() as client:
        tables = client.query_api().query(
            query=flux,
            org=settings.influx_org,
        )

    metadata_by_name: dict[str, dict[str, Any]] = {}

    for table in tables:
        for record in table.records:
            values = record.values

            interface_name = str(
                values.get("ifDescr") or "unknown"
            )

            interface_index = values.get("ifIndex")

            speed_bps = int(
                values.get("ifSpeed") or 0
            )

            admin_status_value = values.get(
                "ifAdminStatus"
            )

            oper_status_value = values.get(
                "ifOperStatus"
            )

            record_time = values.get("_time")

            metadata_by_name[interface_name] = {
                "if_descr": interface_name,
                "if_index": interface_index,
                "admin_status_code": admin_status_value,
                "admin_status": _status_name(
                    admin_status_value
                ),
                "oper_status_code": oper_status_value,
                "oper_status": _status_name(
                    oper_status_value
                ),
                "speed_bps": speed_bps,
                "mtu": int(
                    values.get("ifMtu") or 0
                ),
                "if_type_code": values.get("ifType"),
                "if_type": _interface_type_name(
                    values.get("ifType")
                ),
                "rx_errors": int(
                    values.get("ifInErrors") or 0
                ),
                "tx_errors": int(
                    values.get("ifOutErrors") or 0
                ),
                "last_updated": (
                    record_time.isoformat()
                    if record_time
                    else None
                ),
            }

    traffic_result = get_interface_rates(
        router_ip=router_ip,
        range_minutes=min(range_minutes, 5),
    )

    rates_by_name = {
        item["if_descr"]: item
        for item in traffic_result.get(
            "interfaces",
            [],
        )
    }

    interface_names = set(metadata_by_name)
    interface_names.update(rates_by_name)

    interfaces: list[dict[str, Any]] = []

    for interface_name in interface_names:
        metadata = metadata_by_name.get(
            interface_name,
            {
                "if_descr": interface_name,
                "if_index": None,
                "admin_status_code": None,
                "admin_status": "unknown",
                "oper_status_code": None,
                "oper_status": "unknown",
                "speed_bps": 0,
                "mtu": 0,
                "if_type_code": None,
                "if_type": "unknown",
                "rx_errors": 0,
                "tx_errors": 0,
                "last_updated": None,
            },
        )

        rates = rates_by_name.get(
            interface_name,
            {},
        )

        rx_bps = float(
            rates.get("rx_bps") or 0.0
        )

        tx_bps = float(
            rates.get("tx_bps") or 0.0
        )

        total_bps = rx_bps + tx_bps
        speed_bps = int(
            metadata.get("speed_bps") or 0
        )

        # For full-duplex interfaces, utilization is based
        # on the busiest direction rather than RX + TX.
        utilization_percent = (
            max(rx_bps, tx_bps)
            / speed_bps
            * 100.0
            if speed_bps > 0
            else None
        )

        interfaces.append(
            {
                **metadata,
                "rx_bps": round(rx_bps, 2),
                "tx_bps": round(tx_bps, 2),
                "total_bps": round(
                    total_bps,
                    2,
                ),
                "utilization_percent": (
                    round(
                        utilization_percent,
                        2,
                    )
                    if utilization_percent
                    is not None
                    else None
                ),
                "is_admin_up": (
                    metadata.get(
                        "admin_status"
                    )
                    == "up"
                ),
                "is_oper_up": (
                    metadata.get(
                        "oper_status"
                    )
                    == "up"
                ),
                "has_errors": (
                    int(
                        metadata.get(
                            "rx_errors"
                        )
                        or 0
                    )
                    > 0
                    or int(
                        metadata.get(
                            "tx_errors"
                        )
                        or 0
                    )
                    > 0
                ),
                # Not collected yet by Telegraf.
                "rx_drops": None,
                "tx_drops": None,
                "mac_address": None,
                "last_change": None,
            }
        )

    interfaces.sort(
        key=lambda item: (
            not item["is_oper_up"],
            -item["total_bps"],
            str(item["if_descr"]),
        )
    )

    active_count = sum(
        1
        for item in interfaces
        if item["is_oper_up"]
    )

    error_count = sum(
        1
        for item in interfaces
        if item["has_errors"]
    )

    return {
        "router_ip": router_ip,
        "selected_interface": traffic_result.get(
            "selected_interface"
        ),
        "summary": {
            "total": len(interfaces),
            "operational_up": active_count,
            "operational_down": (
                len(interfaces) - active_count
            ),
            "with_errors": error_count,
            "total_rx_bps": round(
                sum(
                    item["rx_bps"]
                    for item in interfaces
                ),
                2,
            ),
            "total_tx_bps": round(
                sum(
                    item["tx_bps"]
                    for item in interfaces
                ),
                2,
            ),
        },
        "interfaces": interfaces,
    }
