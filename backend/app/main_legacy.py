import os
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from pydantic import BaseModel


INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "SS4TS")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "mikrotik")


app = FastAPI(
    title="SS4TS NOC API",
    description="Backend API for SS4TS Network Operations Center",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


class Device(BaseModel):
    name: str
    ip_address: str
    device_type: str
    site: str
    status: str
    last_seen: str | None = None
    source: str = "influxdb"


def validate_ip(router_ip: str) -> str:
    try:
        return str(IPv4Address(router_ip))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc


def get_influx_client() -> InfluxDBClient:
    if not INFLUX_TOKEN:
        raise RuntimeError("INFLUX_TOKEN is not configured")

    return InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        timeout=15000,
    )


def run_query(flux: str) -> list[Any]:
    with get_influx_client() as client:
        tables = client.query_api().query(
            query=flux,
            org=INFLUX_ORG,
        )

    records: list[Any] = []

    for table in tables:
        records.extend(table.records)

    return records


def escape_flux_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def get_device_records() -> list[Any]:
    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -30d)
  |> filter(fn: (r) =>
      exists r.agent_host and
      exists r.sysName
  )
  |> last()
'''

    return run_query(flux)


def build_devices() -> list[Device]:
    records = get_device_records()
    device_map: dict[str, dict[str, Any]] = {}

    for record in records:
        values = record.values

        ip_address = values.get("agent_host")
        sys_name = values.get("sysName")

        if not ip_address or not sys_name:
            continue

        try:
            ip_address = str(IPv4Address(str(ip_address)))
        except ValueError:
            continue

        record_time = record.get_time()
        existing = device_map.get(ip_address)

        if (
            existing is None
            or (
                record_time
                and existing["last_seen_dt"]
                and record_time > existing["last_seen_dt"]
            )
        ):
            device_map[ip_address] = {
                "name": str(sys_name),
                "ip_address": ip_address,
                "site": str(
                    values.get("sysLocation")
                    or "غير محدد"
                ),
                "last_seen_dt": record_time,
            }

    now = datetime.now(timezone.utc)
    devices: list[Device] = []

    for item in device_map.values():
        last_seen_dt = item["last_seen_dt"]

        if last_seen_dt:
            age_seconds = (
                now - last_seen_dt.astimezone(timezone.utc)
            ).total_seconds()

            status = (
                "online"
                if age_seconds <= 180
                else "offline"
            )
            last_seen = last_seen_dt.isoformat()
        else:
            status = "unknown"
            last_seen = None

        devices.append(
            Device(
                name=item["name"],
                ip_address=item["ip_address"],
                device_type="MikroTik RouterOS",
                site=item["site"],
                status=status,
                last_seen=last_seen,
                source="influxdb",
            )
        )

    return sorted(
        devices,
        key=lambda item: item.name.lower(),
    )


def get_latest_field(
    router_ip: str,
    field_name: str,
    measurement: str | None = None,
) -> tuple[Any, str | None]:
    safe_ip = escape_flux_string(router_ip)
    safe_field = escape_flux_string(field_name)

    measurement_filter = ""

    if measurement:
        safe_measurement = escape_flux_string(measurement)
        measurement_filter = (
            f'|> filter(fn: (r) => '
            f'r._measurement == "{safe_measurement}")'
        )

    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -30d)
  |> filter(fn: (r) =>
      exists r.agent_host and
      r.agent_host == "{safe_ip}"
  )
  {measurement_filter}
  |> filter(fn: (r) => r._field == "{safe_field}")
  |> last()
'''

    records = run_query(flux)

    if not records:
        return None, None

    newest = max(
        records,
        key=lambda record: record.get_time(),
    )

    timestamp = (
        newest.get_time().isoformat()
        if newest.get_time()
        else None
    )

    return newest.get_value(), timestamp


def get_ping_metrics(
    router_ip: str,
) -> dict[str, Any]:
    safe_ip = escape_flux_string(router_ip)

    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "ping")
  |> filter(fn: (r) =>
      (exists r.agent_host and r.agent_host == "{safe_ip}") or
      (exists r.url and r.url == "{safe_ip}") or
      (exists r.url and r.url == "http://{safe_ip}") or
      (exists r.url and r.url == "https://{safe_ip}")
  )
  |> filter(fn: (r) =>
      r._field == "average_response_ms" or
      r._field == "percent_packet_loss" or
      r._field == "result_code"
  )
  |> last()
'''

    records = run_query(flux)

    result = {
        "latency_ms": None,
        "packet_loss": None,
        "result_code": None,
        "last_seen": None,
    }

    latest_time = None

    for record in records:
        field = record.get_field()
        value = record.get_value()

        if field == "average_response_ms":
            result["latency_ms"] = value
        elif field == "percent_packet_loss":
            result["packet_loss"] = value
        elif field == "result_code":
            result["result_code"] = value

        record_time = record.get_time()

        if (
            record_time
            and (
                latest_time is None
                or record_time > latest_time
            )
        ):
            latest_time = record_time

    if latest_time:
        result["last_seen"] = latest_time.isoformat()

    return result


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "SS4TS NOC API",
        "version": "2.0.0",
        "documentation": "/docs",
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    influx_status = "offline"
    influx_error = None

    try:
        with get_influx_client() as client:
            ready = client.ready()
            influx_status = (
                "online"
                if ready.status == "ready"
                else ready.status
            )
    except Exception as exc:
        influx_error = str(exc)

    return {
        "status": (
            "healthy"
            if influx_status == "online"
            else "degraded"
        ),
        "service": "ss4ts-api",
        "influxdb": influx_status,
        "influx_error": influx_error,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/system/status")
async def system_status() -> dict[str, Any]:
    health_data = await health()

    return {
        "status": (
            "operational"
            if health_data["influxdb"] == "online"
            else "degraded"
        ),
        "services": {
            "api": "online",
            "influxdb": health_data["influxdb"],
            "grafana": "unknown",
            "telegraf": "unknown",
        },
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/devices", response_model=list[Device])
async def devices() -> list[Device]:
    try:
        return build_devices()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"InfluxDB query failed: {exc}",
        ) from exc


@app.get(
    "/api/devices/{router_ip}",
    response_model=Device,
)
async def get_device(router_ip: str) -> Device:
    validated_ip = validate_ip(router_ip)

    try:
        all_devices = build_devices()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"InfluxDB query failed: {exc}",
        ) from exc

    device = next(
        (
            item
            for item in all_devices
            if item.ip_address == validated_ip
        ),
        None,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found in InfluxDB",
        )

    return device


@app.get("/api/metrics/{router_ip}")
async def router_metrics(
    router_ip: str,
) -> dict[str, Any]:
    validated_ip = validate_ip(router_ip)

    try:
        all_devices = build_devices()

        device = next(
            (
                item
                for item in all_devices
                if item.ip_address == validated_ip
            ),
            None,
        )

        if device is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found in InfluxDB",
            )

        uptime, uptime_time = get_latest_field(
            validated_ip,
            "sysUptime",
            "mikrotik",
        )

        ping = get_ping_metrics(validated_ip)

        return {
            "router_ip": validated_ip,
            "device_name": device.name,
            "device_type": device.device_type,
            "site": device.site,
            "status": device.status,
            "metrics": {
                "cpu_usage": None,
                "memory_usage": None,
                "temperature": None,
                "uptime_seconds": uptime,
                "rx_bps": None,
                "tx_bps": None,
                "latency_ms": ping["latency_ms"],
                "packet_loss": ping["packet_loss"],
            },
            "availability": {
                "cpu_usage": False,
                "memory_usage": False,
                "temperature": False,
                "uptime_seconds": uptime is not None,
                "rx_bps": False,
                "tx_bps": False,
                "latency_ms": ping["latency_ms"] is not None,
                "packet_loss": ping["packet_loss"] is not None,
            },
            "source": "influxdb",
            "is_live": device.status == "online",
            "last_seen": (
                ping["last_seen"]
                or uptime_time
                or device.last_seen
            ),
            "time": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"InfluxDB query failed: {exc}",
        ) from exc


@app.get("/api/lte/{router_ip}")
async def lte_metrics(
    router_ip: str,
) -> dict[str, Any]:
    validated_ip = validate_ip(router_ip)

    return {
        "router_ip": validated_ip,
        "lte": {
            "operator": None,
            "technology": None,
            "band": None,
            "cell_id": None,
            "pci": None,
            "rsrp": None,
            "rsrq": None,
            "sinr": None,
            "earfcn": None,
        },
        "available": False,
        "message": (
            "LTE data collector is not configured yet"
        ),
        "source": "unavailable",
        "time": datetime.now(timezone.utc).isoformat(),
    }
