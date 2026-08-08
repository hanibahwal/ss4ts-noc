from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel


class NetworkAsset(BaseModel):

    asset_id: str

    ip_address: str

    vendor: str = "Unknown"

    model: Optional[str] = None

    identity: Optional[str] = None

    platform: Optional[str] = None

    version: Optional[str] = None

    architecture: Optional[str] = None

    cpu: Optional[str] = None

    cpu_count: Optional[float] = None

    memory_usage: Optional[float] = None

    uptime: Optional[str] = None

    device_type: Optional[str] = None

    confidence: int = 0

    status: str = "ACTIVE"

    first_seen: str

    last_seen: str


