from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from ipaddress import IPv4Address
from math import isfinite
from typing import Any

from app.models.interface import (
    InterfaceSnapshot,
    normalize_interfaces,
)


class DeviceStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class DevicePlatform(StrEnum):
    MIKROTIK_ROUTEROS = "mikrotik_routeros"
    LINUX = "linux"
    WINDOWS = "windows"
    NETWORK_DEVICE = "network_device"
    UNKNOWN = "unknown"


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(numeric_value):
        return default

    return numeric_value


def _optional_number(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(numeric_value):
        return None

    return numeric_value


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_integer(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _optional_text(
    value: Any,
) -> str | None:
    text = _text(value)

    return text or None


def _percentage(
    value: Any,
) -> float | None:
    numeric_value = _optional_number(
        value
    )

    if numeric_value is None:
        return None

    return round(
        max(
            0.0,
            min(
                numeric_value,
                100.0,
            ),
        ),
        2,
    )


def _normalize_status(
    value: Any,
) -> DeviceStatus:
    normalized = _text(
        value,
        DeviceStatus.UNKNOWN,
    ).lower()

    aliases = {
        "up": "online",
        "running": "online",
        "healthy": "online",
        "reachable": "online",
        "connected": "online",
        "down": "offline",
        "unreachable": "offline",
        "disconnected": "offline",
        "warning": "degraded",
        "degrade": "degraded",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return DeviceStatus(normalized)
    except ValueError:
        return DeviceStatus.UNKNOWN


def _normalize_platform(
    value: Any,
) -> DevicePlatform:
    normalized = _text(
        value,
        DevicePlatform.UNKNOWN,
    ).lower()

    if (
        "routeros" in normalized
        or "mikrotik" in normalized
    ):
        return DevicePlatform.MIKROTIK_ROUTEROS

    if "linux" in normalized:
        return DevicePlatform.LINUX

    if "windows" in normalized:
        return DevicePlatform.WINDOWS

    if normalized in {
        "router",
        "switch",
        "network",
        "network_device",
    }:
        return DevicePlatform.NETWORK_DEVICE

    try:
        return DevicePlatform(normalized)
    except ValueError:
        return DevicePlatform.UNKNOWN


def _validate_ip(
    value: Any,
) -> str:
    text = _text(value)

    if not text:
        return ""

    try:
        return str(
            IPv4Address(text)
        )
    except ValueError:
        return text


def _calculate_memory_usage(
    *,
    explicit_usage: Any,
    total_memory: Any,
    free_memory: Any,
) -> float | None:
    direct_value = _percentage(
        explicit_usage
    )

    if direct_value is not None:
        return direct_value

    total = _optional_number(
        total_memory
    )

    free = _optional_number(
        free_memory
    )

    if (
        total is None
        or total <= 0
        or free is None
    ):
        return None

    used = max(
        0.0,
        total - free,
    )

    return round(
        min(
            used / total * 100.0,
            100.0,
        ),
        2,
    )


def _calculate_storage_usage(
    *,
    explicit_usage: Any,
    total_storage: Any,
    free_storage: Any,
) -> float | None:
    direct_value = _percentage(
        explicit_usage
    )

    if direct_value is not None:
        return direct_value

    total = _optional_number(
        total_storage
    )

    free = _optional_number(
        free_storage
    )

    if (
        total is None
        or total <= 0
        or free is None
    ):
        return None

    used = max(
        0.0,
        total - free,
    )

    return round(
        min(
            used / total * 100.0,
            100.0,
        ),
        2,
    )


@dataclass(slots=True)
class DeviceSnapshot:
    """
    Canonical representation of one monitored device.

    This model is shared by monitoring, health, AI, decision,
    prediction and API layers.
    """

    router_ip: str

    identity: str = "Unknown Device"
    status: DeviceStatus = DeviceStatus.UNKNOWN
    platform: DevicePlatform = DevicePlatform.MIKROTIK_ROUTEROS

    board_name: str | None = None
    model: str | None = None
    architecture: str | None = None
    serial_number: str | None = None

    routeros_version: str | None = None
    firmware_version: str | None = None
    factory_firmware: str | None = None

    uptime: str | None = None
    uptime_seconds: int | None = None

    cpu_name: str | None = None
    cpu_count: int | None = None
    cpu_frequency_mhz: float | None = None
    cpu_usage: float | None = None

    total_memory_bytes: float | None = None
    free_memory_bytes: float | None = None
    memory_usage: float | None = None

    total_storage_bytes: float | None = None
    free_storage_bytes: float | None = None
    storage_usage: float | None = None

    temperature_celsius: float | None = None
    cpu_temperature_celsius: float | None = None
    voltage: float | None = None
    current: float | None = None
    power_watts: float | None = None

    site: str | None = None
    location: str | None = None
    description: str | None = None

    last_seen: str | None = None
    last_updated: str | None = None

    interfaces: list[
        InterfaceSnapshot
    ] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def is_online(self) -> bool:
        return self.status in {
            DeviceStatus.ONLINE,
            DeviceStatus.DEGRADED,
        }

    @property
    def is_degraded(self) -> bool:
        return (
            self.status
            == DeviceStatus.DEGRADED
        )

    @property
    def interface_count(self) -> int:
        return len(
            self.interfaces
        )

    @property
    def operational_interface_count(
        self,
    ) -> int:
        return sum(
            1
            for interface
            in self.interfaces
            if interface.is_oper_up
        )

    @property
    def down_interface_count(
        self,
    ) -> int:
        return sum(
            1
            for interface
            in self.interfaces
            if (
                interface.is_admin_up
                and not interface.is_oper_up
            )
        )

    @property
    def disabled_interface_count(
        self,
    ) -> int:
        return sum(
            1
            for interface
            in self.interfaces
            if not interface.is_admin_up
        )

    @property
    def interfaces_with_errors(
        self,
    ) -> list[InterfaceSnapshot]:
        return [
            interface
            for interface
            in self.interfaces
            if interface.has_errors
        ]

    @property
    def interface_error_count(
        self,
    ) -> int:
        return len(
            self.interfaces_with_errors
        )

    @property
    def total_interface_errors(
        self,
    ) -> int:
        return sum(
            interface.total_errors
            for interface
            in self.interfaces
        )

    @property
    def total_rx_bps(self) -> float:
        return round(
            sum(
                interface.rx_bps
                for interface
                in self.interfaces
            ),
            2,
        )

    @property
    def total_tx_bps(self) -> float:
        return round(
            sum(
                interface.tx_bps
                for interface
                in self.interfaces
            ),
            2,
        )

    @property
    def total_traffic_bps(self) -> float:
        return round(
            self.total_rx_bps
            + self.total_tx_bps,
            2,
        )

    @property
    def high_utilization_interfaces(
        self,
    ) -> list[InterfaceSnapshot]:
        return [
            interface
            for interface
            in self.interfaces
            if (
                interface.utilization_percent
                is not None
                and interface.utilization_percent
                >= 75
            )
        ]

    @property
    def critical_utilization_interfaces(
        self,
    ) -> list[InterfaceSnapshot]:
        return [
            interface
            for interface
            in self.interfaces
            if (
                interface.utilization_percent
                is not None
                and interface.utilization_percent
                >= 90
            )
        ]

    @property
    def health_flags(self) -> list[str]:
        flags: list[str] = []

        if not self.is_online:
            flags.append(
                "device_offline"
            )

        if (
            self.cpu_usage is not None
            and self.cpu_usage >= 95
        ):
            flags.append(
                "cpu_critical"
            )
        elif (
            self.cpu_usage is not None
            and self.cpu_usage >= 85
        ):
            flags.append(
                "cpu_high"
            )
        elif (
            self.cpu_usage is not None
            and self.cpu_usage >= 70
        ):
            flags.append(
                "cpu_elevated"
            )

        if (
            self.memory_usage is not None
            and self.memory_usage >= 95
        ):
            flags.append(
                "memory_critical"
            )
        elif (
            self.memory_usage is not None
            and self.memory_usage >= 85
        ):
            flags.append(
                "memory_high"
            )
        elif (
            self.memory_usage is not None
            and self.memory_usage >= 75
        ):
            flags.append(
                "memory_elevated"
            )

        if (
            self.storage_usage is not None
            and self.storage_usage >= 95
        ):
            flags.append(
                "storage_critical"
            )
        elif (
            self.storage_usage is not None
            and self.storage_usage >= 85
        ):
            flags.append(
                "storage_high"
            )

        if self.down_interface_count:
            flags.append(
                "interfaces_oper_down"
            )

        if self.interface_error_count:
            flags.append(
                "interface_errors"
            )

        if (
            self.critical_utilization_interfaces
        ):
            flags.append(
                "critical_interface_utilization"
            )
        elif (
            self.high_utilization_interfaces
        ):
            flags.append(
                "high_interface_utilization"
            )

        if (
            self.temperature_celsius
            is not None
            and self.temperature_celsius
            >= 80
        ):
            flags.append(
                "temperature_critical"
            )
        elif (
            self.temperature_celsius
            is not None
            and self.temperature_celsius
            >= 70
        ):
            flags.append(
                "temperature_high"
            )

        return flags

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "interface_count":
                self.interface_count,
            "operational_interfaces":
                self.operational_interface_count,
            "down_interfaces":
                self.down_interface_count,
            "disabled_interfaces":
                self.disabled_interface_count,
            "interfaces_with_errors":
                self.interface_error_count,
            "total_interface_errors":
                self.total_interface_errors,
            "high_utilization_interfaces":
                len(
                    self.high_utilization_interfaces
                ),
            "critical_utilization_interfaces":
                len(
                    self.critical_utilization_interfaces
                ),
            "total_rx_bps":
                self.total_rx_bps,
            "total_tx_bps":
                self.total_tx_bps,
            "total_traffic_bps":
                self.total_traffic_bps,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        interfaces: list[
            dict[str, Any]
        ] | None = None,
        default_ip: str = "",
    ) -> DeviceSnapshot:
        """
        Build the canonical device model from RouterOS/API data.
        """

        router_ip = _validate_ip(
            data.get("router_ip")
            or data.get("ip")
            or data.get("ip_address")
            or data.get("host")
            or default_ip
        )

        total_memory = (
            _optional_number(
                data.get(
                    "total_memory_bytes"
                )
                or data.get(
                    "total-memory"
                )
            )
        )

        free_memory = (
            _optional_number(
                data.get(
                    "free_memory_bytes"
                )
                or data.get(
                    "free-memory"
                )
            )
        )

        total_storage = (
            _optional_number(
                data.get(
                    "total_storage_bytes"
                )
                or data.get(
                    "total_hdd_space"
                )
                or data.get(
                    "total-hdd-space"
                )
            )
        )

        free_storage = (
            _optional_number(
                data.get(
                    "free_storage_bytes"
                )
                or data.get(
                    "free_hdd_space"
                )
                or data.get(
                    "free-hdd-space"
                )
            )
        )

        status_value = (
            data.get("status")
        )

        if status_value is None:
            if (
                data.get("is_online")
                is True
            ):
                status_value = (
                    DeviceStatus.ONLINE
                )
            elif (
                data.get("is_online")
                is False
            ):
                status_value = (
                    DeviceStatus.OFFLINE
                )

        interface_data = (
            interfaces
            if interfaces is not None
            else data.get(
                "interfaces",
                [],
            )
        )

        temperature = (
            _optional_number(
                data.get(
                    "temperature_celsius"
                )
                or data.get(
                    "temperature"
                )
            )
        )

        cpu_temperature = (
            _optional_number(
                data.get(
                    "cpu_temperature_celsius"
                )
                or data.get(
                    "cpu_temperature"
                )
                or data.get(
                    "cpu-temperature"
                )
            )
        )

        if (
            temperature is None
            and cpu_temperature
            is not None
        ):
            temperature = (
                cpu_temperature
            )

        return cls(
            router_ip=router_ip,

            identity=_text(
                data.get("identity")
                or data.get("name")
                or data.get(
                    "device_name"
                )
                or router_ip
                or "Unknown Device"
            ),

            status=_normalize_status(
                status_value
            ),

            platform=_normalize_platform(
                data.get("platform")
                or data.get("type")
                or data.get(
                    "device_type"
                )
                or "mikrotik_routeros"
            ),

            board_name=_optional_text(
                data.get("board_name")
                or data.get("board-name")
            ),

            model=_optional_text(
                data.get("model")
                or data.get("board_name")
                or data.get("board-name")
            ),

            architecture=_optional_text(
                data.get("architecture")
                or data.get(
                    "architecture_name"
                )
                or data.get(
                    "architecture-name"
                )
            ),

            serial_number=_optional_text(
                data.get("serial_number")
                or data.get(
                    "serial-number"
                )
            ),

            routeros_version=_optional_text(
                data.get(
                    "routeros_version"
                )
                or data.get("version")
            ),

            firmware_version=_optional_text(
                data.get(
                    "firmware_version"
                )
                or data.get(
                    "current_firmware"
                )
                or data.get(
                    "current-firmware"
                )
            ),

            factory_firmware=_optional_text(
                data.get(
                    "factory_firmware"
                )
                or data.get(
                    "factory-firmware"
                )
            ),

            uptime=_optional_text(
                data.get("uptime")
            ),

            uptime_seconds=_optional_integer(
                data.get(
                    "uptime_seconds"
                )
            ),

            cpu_name=_optional_text(
                data.get("cpu")
                or data.get("cpu_name")
            ),

            cpu_count=_optional_integer(
                data.get("cpu_count")
                or data.get("cpu-count")
            ),

            cpu_frequency_mhz=(
                _optional_number(
                    data.get(
                        "cpu_frequency_mhz"
                    )
                    or data.get(
                        "cpu-frequency"
                    )
                )
            ),

            cpu_usage=_percentage(
                data.get("cpu_usage")
                if data.get("cpu_usage")
                is not None
                else data.get(
                    "cpu_load"
                )
                if data.get("cpu_load")
                is not None
                else data.get(
                    "cpu-load"
                )
            ),

            total_memory_bytes=
                total_memory,

            free_memory_bytes=
                free_memory,

            memory_usage=(
                _calculate_memory_usage(
                    explicit_usage=(
                        data.get(
                            "memory_usage"
                        )
                    ),
                    total_memory=
                        total_memory,
                    free_memory=
                        free_memory,
                )
            ),

            total_storage_bytes=
                total_storage,

            free_storage_bytes=
                free_storage,

            storage_usage=(
                _calculate_storage_usage(
                    explicit_usage=(
                        data.get(
                            "storage_usage"
                        )
                    ),
                    total_storage=
                        total_storage,
                    free_storage=
                        free_storage,
                )
            ),

            temperature_celsius=
                temperature,

            cpu_temperature_celsius=
                cpu_temperature,

            voltage=_optional_number(
                data.get("voltage")
            ),

            current=_optional_number(
                data.get("current")
            ),

            power_watts=_optional_number(
                data.get("power_watts")
                or data.get("power")
            ),

            site=_optional_text(
                data.get("site")
            ),

            location=_optional_text(
                data.get("location")
            ),

            description=_optional_text(
                data.get("description")
            ),

            last_seen=_optional_text(
                data.get("last_seen")
            ),

            last_updated=_optional_text(
                data.get("last_updated")
            ),

            interfaces=normalize_interfaces(
                interface_data
                if isinstance(
                    interface_data,
                    list,
                )
                else []
            ),

            metadata=(
                dict(
                    data.get(
                        "metadata",
                        {},
                    )
                )
                if isinstance(
                    data.get(
                        "metadata",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
        )

    def to_dict(
        self,
        *,
        include_interfaces: bool = True,
    ) -> dict[str, Any]:
        """
        Serialize the canonical device model for APIs and engines.
        """

        result = asdict(self)

        result["status"] = (
            self.status.value
        )

        result["platform"] = (
            self.platform.value
        )

        result.update(
            {
                "ip": self.router_ip,
                "device_name":
                    self.identity,
                "is_online":
                    self.is_online,
                "is_degraded":
                    self.is_degraded,
                "health_flags":
                    self.health_flags,
                "summary":
                    self.summary,
            }
        )

        if include_interfaces:
            result["interfaces"] = [
                interface.to_dict()
                for interface
                in self.interfaces
            ]
        else:
            result.pop(
                "interfaces",
                None,
            )

        return result
