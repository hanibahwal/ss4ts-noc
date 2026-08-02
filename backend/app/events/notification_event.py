from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.events.notification_enums import (
    EventSeverity,
    EventSource,
    EventState,
    EventType,
)
from app.events.notification_fingerprint import (
    build_notification_fingerprint,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class DeviceReference(ContractModel):
    id: int | str
    name: str = Field(min_length=1, max_length=200)
    hostname: str | None = Field(default=None, max_length=255)
    ip: str | None = Field(default=None, max_length=64)
    role: str | None = Field(default=None, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)


class SiteReference(ContractModel):
    id: int | str
    name: str = Field(min_length=1, max_length=200)
    region: str | None = Field(default=None, max_length=150)


class InterfaceReference(ContractModel):
    id: int | str
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class MetricContext(ContractModel):
    name: str = Field(min_length=1, max_length=100)
    value: float | int | str | bool | None = None
    threshold: float | int | str | bool | None = None
    unit: str | None = Field(default=None, max_length=50)


class NotificationEvent(ContractModel):
    """
    Canonical notification event exchanged by all SS4TS NOC monitors.

    The object is immutable after validation. Downstream systems must create
    a new event when state or measured values change.
    """

    schema_version: Literal["1.0"] = "1.0"

    event_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID | None = None
    fingerprint: str | None = Field(default=None, max_length=500)

    event_type: EventType
    state: EventState
    severity: EventSeverity
    source: EventSource

    device: DeviceReference | None = None
    site: SiteReference | None = None
    interface: InterfaceReference | None = None
    metric: MetricContext | None = None

    title: str = Field(min_length=1, max_length=250)
    message: str = Field(min_length=1, max_length=4000)

    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    occurred_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("occurred_at", "created_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Notification event timestamps must be timezone-aware"
            )

        return value.astimezone(timezone.utc)

    @field_validator("labels")
    @classmethod
    def validate_labels(
        cls,
        labels: dict[str, str],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}

        for key, value in labels.items():
            normalized_key = str(key).strip()
            normalized_value = str(value).strip()

            if not normalized_key:
                raise ValueError("Notification label keys cannot be empty")

            if len(normalized_key) > 100:
                raise ValueError(
                    "Notification label keys cannot exceed 100 characters"
                )

            if len(normalized_value) > 500:
                raise ValueError(
                    "Notification label values cannot exceed 500 characters"
                )

            normalized[normalized_key] = normalized_value

        return normalized

    @model_validator(mode="after")
    def finalize_contract(self) -> "NotificationEvent":
        event_type_value = self.event_type.value

        device_required = (
            event_type_value.startswith("device_")
            or event_type_value.startswith("interface_")
            or self.event_type
            in {
                EventType.PING_TIMEOUT,
                EventType.HIGH_LATENCY,
                EventType.PACKET_LOSS,
                EventType.LATENCY_RECOVERED,
                EventType.HIGH_CPU,
                EventType.HIGH_MEMORY,
                EventType.HIGH_TEMPERATURE,
                EventType.HIGH_VOLTAGE,
                EventType.FAN_FAILURE,
                EventType.POWER_SUPPLY_FAILURE,
                EventType.HIGH_BANDWIDTH,
                EventType.LOW_BANDWIDTH,
                EventType.TRAFFIC_DROP,
                EventType.TRAFFIC_SPIKE,
                EventType.LOW_SIGNAL,
                EventType.INTERFERENCE_DETECTED,
                EventType.CELL_CHANGED,
                EventType.BAND_CHANGED,
                EventType.SIGNAL_DEGRADED,
                EventType.OPERATOR_CHANGED,
                EventType.CARRIER_LOST,
            }
        )

        if device_required and self.device is None:
            raise ValueError(
                f"Event type '{event_type_value}' requires a device"
            )

        if (
            event_type_value.startswith("interface_")
            and self.interface is None
        ):
            raise ValueError(
                f"Event type '{event_type_value}' requires an interface"
            )

        if self.correlation_id is None:
            object.__setattr__(
                self,
                "correlation_id",
                self.event_id,
            )

        if self.fingerprint is None:
            object.__setattr__(
                self,
                "fingerprint",
                build_notification_fingerprint(
                    event_type=self.event_type,
                    device_id=(
                        self.device.id
                        if self.device is not None
                        else None
                    ),
                    interface_id=(
                        self.interface.id
                        if self.interface is not None
                        else None
                    ),
                    metric_name=(
                        self.metric.name
                        if self.metric is not None
                        else None
                    ),
                    source=self.source,
                ),
            )

        return self

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json",
            exclude_none=True,
        )
