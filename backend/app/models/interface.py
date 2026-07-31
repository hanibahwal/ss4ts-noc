from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from math import isfinite
from typing import Any


class InterfaceStatus(StrEnum):
    UP = "up"
    DOWN = "down"
    TESTING = "testing"
    UNKNOWN = "unknown"
    DORMANT = "dormant"
    NOT_PRESENT = "not_present"
    LOWER_LAYER_DOWN = "lower_layer_down"


class InterfaceKind(StrEnum):
    ETHERNET = "ethernet"
    BRIDGE = "bridge"
    VLAN = "vlan"
    WIFI = "wifi"
    PPP = "ppp"
    TUNNEL = "tunnel"
    LOOPBACK = "software_loopback"
    VIRTUAL = "virtual"
    OTHER = "other"
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


def _optional_number(
    value: Any,
) -> float | None:
    if value is None:
        return None

    numeric_value = _number(
        value,
        default=float("nan"),
    )

    if not isfinite(numeric_value):
        return None

    return numeric_value


def _normalize_status(
    value: Any,
) -> InterfaceStatus:
    normalized = str(
        value or InterfaceStatus.UNKNOWN
    ).strip().lower()

    aliases = {
        "notpresent": "not_present",
        "lowerlayerdown": "lower_layer_down",
        "lower-layer-down": "lower_layer_down",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return InterfaceStatus(normalized)
    except ValueError:
        return InterfaceStatus.UNKNOWN


def _normalize_kind(
    value: Any,
) -> InterfaceKind:
    normalized = str(
        value or InterfaceKind.UNKNOWN
    ).strip().lower()

    aliases = {
        "wireless": "wifi",
        "wlan": "wifi",
        "ether": "ethernet",
        "software-loopback": "software_loopback",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return InterfaceKind(normalized)
    except ValueError:
        if normalized.startswith("type_"):
            return InterfaceKind.OTHER

        return InterfaceKind.UNKNOWN


@dataclass(slots=True)
class InterfaceSnapshot:
    """
    Canonical SS4TS representation of one network interface.

    Monitoring services, AI engines, decision engines and API layers
    should exchange this model instead of unstructured dictionaries.
    """

    name: str
    index: int | None = None

    kind: InterfaceKind = InterfaceKind.UNKNOWN

    admin_status: InterfaceStatus = InterfaceStatus.UNKNOWN
    oper_status: InterfaceStatus = InterfaceStatus.UNKNOWN

    speed_bps: float = 0.0
    mtu: int = 0

    rx_bps: float = 0.0
    tx_bps: float = 0.0

    rx_errors: int = 0
    tx_errors: int = 0

    rx_drops: int | None = None
    tx_drops: int | None = None

    mac_address: str | None = None
    last_updated: str | None = None
    last_change: str | None = None

    description: str | None = None
    alias: str | None = None

    @property
    def is_admin_up(self) -> bool:
        return self.admin_status == InterfaceStatus.UP

    @property
    def is_oper_up(self) -> bool:
        return self.oper_status == InterfaceStatus.UP

    @property
    def total_bps(self) -> float:
        return max(
            0.0,
            self.rx_bps + self.tx_bps,
        )

    @property
    def total_errors(self) -> int:
        return max(
            0,
            self.rx_errors + self.tx_errors,
        )

    @property
    def total_drops(self) -> int | None:
        if (
            self.rx_drops is None
            and self.tx_drops is None
        ):
            return None

        return (
            (self.rx_drops or 0)
            + (self.tx_drops or 0)
        )

    @property
    def has_errors(self) -> bool:
        return self.total_errors > 0

    @property
    def has_drops(self) -> bool:
        return bool(
            self.total_drops
            and self.total_drops > 0
        )

    @property
    def utilization_percent(self) -> float | None:
        """
        For full-duplex links, utilization is calculated from the
        busiest direction rather than RX + TX.
        """
        if self.speed_bps <= 0:
            return None

        utilization = (
            max(
                self.rx_bps,
                self.tx_bps,
            )
            / self.speed_bps
            * 100.0
        )

        return round(
            max(
                0.0,
                min(utilization, 100.0),
            ),
            2,
        )

    @property
    def state(self) -> str:
        if not self.is_admin_up:
            return "administratively_down"

        if self.is_oper_up:
            if self.total_bps > 0:
                return "active"

            return "up"

        return "down"

    @property
    def health_flags(self) -> list[str]:
        flags: list[str] = []

        if (
            self.is_admin_up
            and not self.is_oper_up
        ):
            flags.append(
                "admin_up_oper_down"
            )

        if self.has_errors:
            flags.append(
                "interface_errors"
            )

        if self.has_drops:
            flags.append(
                "packet_drops"
            )

        utilization = (
            self.utilization_percent
        )

        if (
            utilization is not None
            and utilization >= 90
        ):
            flags.append(
                "critical_utilization"
            )
        elif (
            utilization is not None
            and utilization >= 75
        ):
            flags.append(
                "high_utilization"
            )

        return flags

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> InterfaceSnapshot:
        """
        Build the canonical model from current API, SNMP or InfluxDB
        interface dictionaries.
        """
        rx_bps = max(
            0.0,
            _number(
                data.get("rx_bps")
            ),
        )

        tx_bps = max(
            0.0,
            _number(
                data.get("tx_bps")
            ),
        )

        admin_status = _normalize_status(
            data.get("admin_status")
        )

        oper_status = _normalize_status(
            data.get("oper_status")
        )

        if (
            data.get("is_admin_up") is True
            and admin_status
            == InterfaceStatus.UNKNOWN
        ):
            admin_status = InterfaceStatus.UP

        if (
            data.get("is_oper_up") is True
            and oper_status
            == InterfaceStatus.UNKNOWN
        ):
            oper_status = InterfaceStatus.UP

        return cls(
            name=str(
                data.get("if_descr")
                or data.get("if_name")
                or data.get("name")
                or "unknown"
            ),
            index=_optional_integer(
                data.get("if_index")
                or data.get("index")
            ),
            kind=_normalize_kind(
                data.get("if_type")
                or data.get("kind")
                or data.get("type")
            ),
            admin_status=admin_status,
            oper_status=oper_status,
            speed_bps=max(
                0.0,
                _number(
                    data.get("speed_bps")
                    or data.get("if_speed")
                ),
            ),
            mtu=max(
                0,
                _integer(
                    data.get("mtu")
                ),
            ),
            rx_bps=rx_bps,
            tx_bps=tx_bps,
            rx_errors=max(
                0,
                _integer(
                    data.get("rx_errors")
                ),
            ),
            tx_errors=max(
                0,
                _integer(
                    data.get("tx_errors")
                ),
            ),
            rx_drops=_optional_integer(
                data.get("rx_drops")
            ),
            tx_drops=_optional_integer(
                data.get("tx_drops")
            ),
            mac_address=(
                str(
                    data.get(
                        "mac_address"
                    )
                )
                if data.get(
                    "mac_address"
                )
                else None
            ),
            last_updated=(
                str(
                    data.get(
                        "last_updated"
                    )
                )
                if data.get(
                    "last_updated"
                )
                else None
            ),
            last_change=(
                str(
                    data.get(
                        "last_change"
                    )
                )
                if data.get(
                    "last_change"
                )
                else None
            ),
            description=(
                str(
                    data.get(
                        "description"
                    )
                )
                if data.get(
                    "description"
                )
                else None
            ),
            alias=(
                str(
                    data.get(
                        "alias"
                    )
                )
                if data.get(
                    "alias"
                )
                else None
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the model using the field names currently expected
        by SS4TS APIs and frontend components.
        """
        result = asdict(self)

        result["kind"] = self.kind.value
        result["admin_status"] = (
            self.admin_status.value
        )
        result["oper_status"] = (
            self.oper_status.value
        )

        result.update(
            {
                "if_descr": self.name,
                "if_index": self.index,
                "if_type": self.kind.value,
                "is_admin_up":
                    self.is_admin_up,
                "is_oper_up":
                    self.is_oper_up,
                "total_bps":
                    round(
                        self.total_bps,
                        2,
                    ),
                "total_errors":
                    self.total_errors,
                "total_drops":
                    self.total_drops,
                "has_errors":
                    self.has_errors,
                "has_drops":
                    self.has_drops,
                "utilization_percent":
                    self.utilization_percent,
                "state": self.state,
                "health_flags":
                    self.health_flags,
            }
        )

        return result


def normalize_interfaces(
    interfaces: list[
        dict[str, Any]
    ] | None,
) -> list[InterfaceSnapshot]:
    """
    Normalize a complete interfaces collection while ignoring invalid
    non-dictionary entries.
    """
    return [
        InterfaceSnapshot.from_dict(
            item
        )
        for item in (
            interfaces or []
        )
        if isinstance(
            item,
            dict,
        )
    ]
