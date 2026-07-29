import os


class Settings:
    app_name: str = "SS4TS NOC API"
    app_version: str = "3.0.0"

    influx_url: str = os.getenv("INFLUX_URL", "http://influxdb:8086")
    influx_token: str = os.getenv("INFLUX_TOKEN", "")
    influx_org: str = os.getenv("INFLUX_ORG", "SS4TS")
    influx_bucket: str = os.getenv("INFLUX_BUCKET", "mikrotik")

    snapshot_cache_seconds: int = int(
        os.getenv("SNAPSHOT_CACHE_SECONDS", "15")
    )

    device_online_after_seconds: int = int(
        os.getenv("DEVICE_ONLINE_AFTER_SECONDS", "180")
    )


settings = Settings()
