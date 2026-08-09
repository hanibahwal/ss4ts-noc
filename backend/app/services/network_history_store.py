"""
Network History Store
H23.4.5.5.12.X.4.2.1

Stores historical network intelligence data
for Predictive Network Intelligence Engine.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


DB_FILE = DATA_DIR / "network_history.db"


# H24 Single Device Validation Mode
ACTIVE_DEVICE_FILTER = "192.168.45.99"


def get_connection():
    """
    Create database connection
    """
    return sqlite3.connect(DB_FILE)


def initialize_database():
    """
    Create historical metrics table
    """

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS network_metrics_history (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                device_ip TEXT NOT NULL,

                device_name TEXT,

                timestamp TEXT NOT NULL,

                cpu REAL DEFAULT 0,

                memory REAL DEFAULT 0,

                traffic_rx REAL DEFAULT 0,

                traffic_tx REAL DEFAULT 0,

                users INTEGER DEFAULT 0,

                latency REAL DEFAULT 0,

                packet_loss REAL DEFAULT 0,

                signal REAL DEFAULT 0,

                status TEXT DEFAULT 'unknown'

            )
            """
        )

        conn.commit()


def save_metric(
    device_ip: str,
    device_name: str = "",
    cpu: float = 0,
    memory: float = 0,
    traffic_rx: float = 0,
    traffic_tx: float = 0,
    users: int = 0,
    latency: float = 0,
    packet_loss: float = 0,
    signal: float = 0,
    status: str = "online",
):
    """
    Save one network measurement
    """

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO network_metrics_history
            (
                device_ip,
                device_name,
                timestamp,
                cpu,
                memory,
                traffic_rx,
                traffic_tx,
                users,
                latency,
                packet_loss,
                signal,
                status
            )

            VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?)

            """,
            (
                device_ip,
                device_name,
                datetime.utcnow().isoformat(),
                cpu,
                memory,
                traffic_rx,
                traffic_tx,
                users,
                latency,
                packet_loss,
                signal,
                status,
            ),
        )

        conn.commit()


def get_history(
    device_ip: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Return device history
    """

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM network_metrics_history

            WHERE device_ip = ?

            ORDER BY id DESC

            LIMIT ?

            """,
            (
                device_ip,
                limit,
            ),
        ).fetchall()


        return [
            dict(row)
            for row in rows
        ]


def get_all_devices_summary():
    """
    Return latest status of all devices.

    H24 Single Device Validation:
    Only HANI-HOME-OFFICE is exposed
    to the Dashboard.
    """

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT

                device_ip,

                device_name,

                MAX(timestamp) AS last_seen,

                AVG(cpu) AS avg_cpu,

                AVG(traffic_rx) AS avg_rx,

                AVG(traffic_tx) AS avg_tx


            FROM network_metrics_history


            WHERE device_ip = ?


            GROUP BY device_ip

            """,
            (
                ACTIVE_DEVICE_FILTER,
            ),
        ).fetchall()


        return [
            dict(row)
            for row in rows
        ]


# Initialize database automatically
initialize_database()
