from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sqlite3
import uuid
import os


# ==========================================================
# SS4TS Enterprise Fleet Device Registry
# H23.4.5.5.12.X.4.8
# Persistent Fleet Inventory Database
# ==========================================================


DEFAULT_DATA_DIR = Path(
    os.getenv(
        "SS4TS_DATA_DIR",
        "./data",
    )
)


DB_PATH = Path(
    os.getenv(
        "SS4TS_FLEET_DB",
        str(
            DEFAULT_DATA_DIR
            / "fleet-registry.db"
        ),
    )
)


ENGINE_NAME = (
    "SS4TS Enterprise Fleet Device Registry"
)


ENGINE_VERSION = (
    "1.0.0-production"
)


# ==========================================================
# Time Helper
# ==========================================================

def _now():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==========================================================
# Database Initialization
# ==========================================================

def _init_db():

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fleet_devices
            (

            id TEXT PRIMARY KEY,

            hostname TEXT,

            router_ip TEXT UNIQUE,

            site TEXT,

            model TEXT,

            role TEXT,

            status TEXT,

            health_score INTEGER,

            last_seen TEXT,

            created_at TEXT

            )
            """
        )


        conn.commit()



_init_db()



# ==========================================================
# Register Device
# ==========================================================

def register_device(
    *,
    hostname: str,
    router_ip: str,
    site: str,
    model: str,
    role: str,
    status: str = "UNKNOWN",
    health_score: int = 0,
):


    device_id = str(
        uuid.uuid4()
    )


    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            INSERT OR REPLACE INTO fleet_devices
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (

                device_id,
                hostname,
                router_ip,
                site,
                model,
                role,
                status,
                health_score,
                _now(),
                _now(),

            )
        )


        conn.commit()



    return device_id



# ==========================================================
# Update Device Health
# ==========================================================

def update_device_health(
    router_ip: str,
    health_score: int,
    status: str,
):


    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            UPDATE fleet_devices

            SET

            health_score=?,

            status=?,

            last_seen=?

            WHERE router_ip=?

            """,
            (

                health_score,
                status,
                _now(),
                router_ip,

            )
        )


        conn.commit()



# ==========================================================
# Get Device
# ==========================================================

def get_device(
    router_ip: str
):


    with sqlite3.connect(DB_PATH) as conn:

        row = conn.execute(
            """
            SELECT *
            FROM fleet_devices
            WHERE router_ip=?
            """,
            (
                router_ip,
            )
        ).fetchone()



    if not row:

        return None



    return {

        "device_id": row[0],
        "hostname": row[1],
        "router_ip": row[2],
        "site": row[3],
        "model": row[4],
        "role": row[5],
        "status": row[6],
        "health_score": row[7],
        "last_seen": row[8],
        "created_at": row[9],

    }



# ==========================================================
# List Devices
# ==========================================================

def list_devices():


    with sqlite3.connect(DB_PATH) as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM fleet_devices
            ORDER BY created_at DESC
            """
        ).fetchall()



    return [

        {

            "device_id": r[0],
            "hostname": r[1],
            "router_ip": r[2],
            "site": r[3],
            "model": r[4],
            "role": r[5],
            "status": r[6],
            "health_score": r[7],
            "last_seen": r[8],
            "created_at": r[9],

        }

        for r in rows

    ]
