from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Any

from app.core.config import settings
from app.services.influx import get_influx_client


PING_FIELDS = {
    "average_response_ms",
    "maximum_response_ms",
    "minimum_response_ms",
    "packets_received",
    "packets_transmitted",
    "percent_packet_loss",
    "result_code",
    "standard_deviation_ms",
    "ttl",
}


def _flux_string(value: str) -> str:
    """Escape a string before embedding it in a Flux query."""
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_ping_metrics(
    target: str,
    *,
    range_minutes: int = 5,
) -> dict[str, Any]:
    """
    Return the newest Telegraf Ping metrics stored in InfluxDB.

    The returned reachability is determined from:
    - result_code
    - packets_received
    - percent_packet_loss
    """

    validated_target = str(IPv4Address(target))

    safe_target = _flux_string(validated_target)
    safe_bucket = _flux_string(settings.influx_bucket)

    range_minutes = max(1, min(int(range_minutes), 1440))

    flux = f'''
from(bucket: "{safe_bucket}")
  |> range(start: -{range_minutes}m)
  |> filter(fn: (r) =>
    r._measurement == "ping" and
    r.url == "{safe_target}"
  )
  |> filter(fn: (r) =>
    r._field == "average_response_ms" or
    r._field == "maximum_response_ms" or
    r._field == "minimum_response_ms" or
    r._field == "packets_received" or
    r._field == "packets_transmitted" or
    r._field == "percent_packet_loss" or
    r._field == "result_code" or
    r._field == "standard_deviation_ms" or
    r._field == "ttl"
  )
  |> group(columns: ["_field"])
  |> last()
'''

    with get_influx_client() as client:
        tables = client.query_api().query(
            query=flux,
            org=settings.influx_org,
        )

    values: dict[str, Any] = {}
    newest_time: datetime | None = None
    source_host: str | None = None

    for table in tables:
        for record in table.records:
            field = record.get_field()

            if field not in PING_FIELDS:
                continue

            values[field] = record.get_value()

            record_time = record.get_time()

            if (
                record_time is not None
                and (
                    newest_time is None
                    or record_time > newest_time
                )
            ):
                newest_time = record_time

            source_host = (
                source_host
                or record.values.get("host")
            )

    if not values:
        raise RuntimeError(
            "No recent Ping data found in InfluxDB "
            f"for target {validated_target}"
        )

    transmitted = _int_or_none(
        values.get("packets_transmitted")
    )
    received = _int_or_none(
        values.get("packets_received")
    )
    packet_loss = _float_or_none(
        values.get("percent_packet_loss")
    )
    result_code = _int_or_none(
        values.get("result_code")
    )

    reachable = (
        result_code == 0
        and received is not None
        and received > 0
        and (
            packet_loss is None
            or packet_loss < 100.0
        )
    )

    return {
        "available": True,
        "reachable": reachable,
        "latency_ms": _float_or_none(
            values.get("average_response_ms")
        ),
        "minimum_latency_ms": _float_or_none(
            values.get("minimum_response_ms")
        ),
        "maximum_latency_ms": _float_or_none(
            values.get("maximum_response_ms")
        ),
        "standard_deviation_ms": _float_or_none(
            values.get("standard_deviation_ms")
        ),
        "packet_loss_percent": packet_loss,
        "packets_transmitted": transmitted,
        "packets_received": received,
        "result_code": result_code,
        "ttl": _int_or_none(values.get("ttl")),
        "target": validated_target,
        "sample_time": (
            newest_time.isoformat()
            if newest_time is not None
            else None
        ),
        "source_host": source_host,
        "source": "influxdb_telegraf_ping",
    }
