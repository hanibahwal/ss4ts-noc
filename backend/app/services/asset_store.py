from datetime import datetime, timezone
import sqlite3
from app.services.data_directory import data_path
from typing import Any


DB_PATH = data_path(
    "network_assets.db"
)


class AssetStore:
    """
    SS4TS-NOC Persistent Asset Inventory Store

    H29.4:
    - Persistent network asset database
    - Auto update discovered assets
    - Full fingerprint synchronization
    """


    def __init__(self):

        DB_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self._init_db()



    def _connect(self):

        return sqlite3.connect(
            DB_PATH
        )



    def _init_db(self):

        with self._connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS network_assets (

                    asset_id TEXT PRIMARY KEY,

                    ip_address TEXT UNIQUE,

                    vendor TEXT,

                    model TEXT,

                    identity TEXT,

                    platform TEXT,

                    version TEXT,

                    architecture TEXT,

                    cpu TEXT,

                    cpu_count REAL,

                    memory_usage REAL,

                    uptime TEXT,

                    device_type TEXT,

                    confidence INTEGER,

                    status TEXT,

                    first_seen TEXT,

                    last_seen TEXT

                )
                """
            )



    def save(
        self,
        asset: dict[str, Any]
    ):

        now = datetime.now(
            timezone.utc
        ).isoformat()



        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO network_assets
                VALUES
                (
                    :asset_id,
                    :ip_address,
                    :vendor,
                    :model,
                    :identity,
                    :platform,
                    :version,
                    :architecture,
                    :cpu,
                    :cpu_count,
                    :memory_usage,
                    :uptime,
                    :device_type,
                    :confidence,
                    :status,
                    :first_seen,
                    :last_seen
                )


                ON CONFLICT(ip_address)
                DO UPDATE SET


                    vendor=excluded.vendor,

                    model=excluded.model,

                    identity=excluded.identity,

                    platform=excluded.platform,

                    version=excluded.version,

                    architecture=excluded.architecture,

                    cpu=excluded.cpu,

                    cpu_count=excluded.cpu_count,

                    memory_usage=excluded.memory_usage,

                    uptime=excluded.uptime,

                    device_type=excluded.device_type,

                    confidence=excluded.confidence,

                    status='ACTIVE',

                    last_seen=:last_seen


                """,
                {
                    **asset,
                    "last_seen": now
                }
            )



    def list_all(self):

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM network_assets
                ORDER BY last_seen DESC
                """
            ).fetchall()


        return rows



asset_store = AssetStore()
