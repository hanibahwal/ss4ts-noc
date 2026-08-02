from __future__ import annotations

from enum import StrEnum


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class EventState(StrEnum):
    FIRING = "firing"
    ACTIVE = "active"
    RECOVERED = "recovered"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class EventSource(StrEnum):
    PING_MONITOR = "ping-monitor"
    SNMP_MONITOR = "snmp-monitor"
    TRAFFIC_MONITOR = "traffic-monitor"
    LTE_MONITOR = "lte-monitor"
    SYSLOG = "syslog"
    API = "api"
    MANUAL = "manual"
    SYSTEM = "system"


class EventType(StrEnum):
    # Device events
    DEVICE_UP = "device_up"
    DEVICE_DOWN = "device_down"
    DEVICE_REACHABLE = "device_reachable"
    DEVICE_UNREACHABLE = "device_unreachable"
    DEVICE_ADDED = "device_added"
    DEVICE_REMOVED = "device_removed"
    DEVICE_DISABLED = "device_disabled"
    DEVICE_ENABLED = "device_enabled"

    # Interface events
    INTERFACE_UP = "interface_up"
    INTERFACE_DOWN = "interface_down"
    INTERFACE_ERROR = "interface_error"
    INTERFACE_SPEED_CHANGED = "interface_speed_changed"
    INTERFACE_DUPLEX_CHANGED = "interface_duplex_changed"

    # Ping events
    PING_TIMEOUT = "ping_timeout"
    HIGH_LATENCY = "high_latency"
    PACKET_LOSS = "packet_loss"
    LATENCY_RECOVERED = "latency_recovered"

    # Resource and SNMP events
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_TEMPERATURE = "high_temperature"
    HIGH_VOLTAGE = "high_voltage"
    FAN_FAILURE = "fan_failure"
    POWER_SUPPLY_FAILURE = "power_supply_failure"

    # Traffic events
    HIGH_BANDWIDTH = "high_bandwidth"
    LOW_BANDWIDTH = "low_bandwidth"
    TRAFFIC_DROP = "traffic_drop"
    TRAFFIC_SPIKE = "traffic_spike"

    # Wireless events
    WIRELESS_CLIENT_CONNECTED = "wireless_client_connected"
    WIRELESS_CLIENT_DISCONNECTED = "wireless_client_disconnected"
    LOW_SIGNAL = "low_signal"
    INTERFERENCE_DETECTED = "interference_detected"

    # LTE / 5G events
    CELL_CHANGED = "cell_changed"
    BAND_CHANGED = "band_changed"
    SIGNAL_DEGRADED = "signal_degraded"
    OPERATOR_CHANGED = "operator_changed"
    CARRIER_LOST = "carrier_lost"

    # Platform events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    BACKUP_COMPLETED = "backup_completed"
    BACKUP_FAILED = "backup_failed"
    DATABASE_ERROR = "database_error"
