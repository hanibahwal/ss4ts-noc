from influxdb_client import InfluxDBClient

from app.core.config import settings


def get_influx_client() -> InfluxDBClient:
    if not settings.influx_token:
        raise RuntimeError("INFLUX_TOKEN is not configured")

    return InfluxDBClient(
        url=settings.influx_url,
        token=settings.influx_token,
        org=settings.influx_org,
    )
