from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from statistics import mean, median
from typing import Any


class TrafficDirection(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    UNKNOWN = "unknown"


class TrafficQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"
    EMPTY = "empty"


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try: numeric_value = float(value)
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

    try: numeric_value = float(value)
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


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            value,
            maximum,
        ),
    )


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)

        if not text:
            return None

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                text
            )
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )

def _datetime_to_iso(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.astimezone(
        timezone.utc
    ).isoformat()


def _percentile(
    values: list[float],
    percentile: float,
) -> float:
    """
    Calculate a percentile using linear interpolation.

    percentile: 0.0 = minimum
        0.95 = P95
        1.0 = maximum
    """
    if not values:
        return 0.0

    ordered = sorted(
        _number(value)
        for value in values
    )

    if len(ordered) == 1:
        return ordered[0]

    percentile = max(
        0.0,
        min(
            percentile,
            1.0,
        ),
    )

    position = (
        percentile
        * (len(ordered) - 1)
    )

    lower_index = int(position)
    upper_index = min(
        lower_index + 1,
        len(ordered) - 1,
    )

    fraction = (
        position - lower_index
    )

    return (
        ordered[lower_index]
        + (
            ordered[upper_index]
            - ordered[lower_index]
        )
        * fraction
    )


def _linear_regression_slope(
    values: list[float],
) -> float:
    if len(values) < 2:
        return 0.0

    x_values = list(
        range(len(values))
    )

    x_mean = mean(
        x_values
    )

    y_mean = mean(
        values
    )

    numerator = sum(
        (
            x_value - x_mean
        )
        * (
            y_value - y_mean
        )
        for x_value, y_value
        in zip(
            x_values,
            values,
            strict=False,
        )
    )

    denominator = sum(
        (
            x_value - x_mean
        ) ** 2
        for x_value
        in x_values
    )

    if denominator == 0:
        return 0.0

    return numerator / denominator


@dataclass(slots=True)
class TrafficPoint:
    """
    Canonical traffic point representing one aggregated time sample.
    """

    time: datetime | None

    rx_bps: float = 0.0
    tx_bps: float = 0.0

    interface_name: str | None = None

    sample_seconds: int | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def total_bps(self) -> float:
        return round(
            max(
                0.0,
                self.rx_bps,
            )
            + max(
                0.0,
                self.tx_bps,
            ),
            2,
        )

    @property
    def dominant_direction(
        self,
    ) -> str:
        if self.rx_bps > self.tx_bps:
            return "rx"

        if self.tx_bps > self.rx_bps:
            return "tx"

        return "balanced"

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        default_interface: str | None = None,
        default_window_seconds: int | None = None,
    ) -> TrafficPoint:
        return cls(
            time=_parse_datetime(
                data.get("time")
                or data.get("_time")
                or data.get(
                    "timestamp"
                )
            ),

            rx_bps=max(
                0.0,
                _number(
                    data.get("rx_bps")
                    or data.get("receive_bps")
                    or data.get("download_bps")
                ),
            ),

            tx_bps=max(
                0.0,
                _number(
                    data.get("tx_bps")
                    or data.get("transmit_bps")
                    or data.get("upload_bps")
                ),
            ),

            interface_name=(
                _text(
                    data.get(
                        "interface_name"
                    )
                    or data.get(
                        "interface"
                    )
                    or data.get(
                        "if_descr"
                    )
                    or default_interface
                )
                or None
            ),

            sample_seconds=(
                max(
                    1,
                    _integer(
                        data.get(
                            "sample_seconds"
                        )
                        or data.get(
                            "window_seconds"
                        )
                        or default_window_seconds
                    ),
                )
                if (
                    data.get(
                        "sample_seconds"
                    )
                    is not None
                    or data.get(
                        "window_seconds"
                    )
                    is not None
                    or default_window_seconds
                    is not None
                )
                else None
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
    ) -> dict[str, Any]:
        result = asdict(self)

        result["time"] = (
            _datetime_to_iso(
                self.time
            )
        )

        result["total_bps"] = (
            self.total_bps
        )

        result[
            "dominant_direction"
        ] = self.dominant_direction

        return result


@dataclass(slots=True)
class TrafficStatistics:
    """
    Statistical summary for RX, TX or total traffic values.
    """

    count: int = 0

    minimum_bps: float = 0.0
    maximum_bps: float = 0.0

    average_bps: float = 0.0
    median_bps: float = 0.0

    p75_bps: float = 0.0
    p90_bps: float = 0.0
    p95_bps: float = 0.0
    p99_bps: float = 0.0

    latest_bps: float = 0.0
    first_bps: float = 0.0

    @classmethod
    def from_values(
        cls,
        values: list[float],
    ) -> TrafficStatistics:
        clean_values = [
            max(
                0.0,
                _number(value),
            )
            for value in values
        ]

        if not clean_values:
            return cls()

        return cls(
            count=len(
                clean_values
            ),

            minimum_bps=round(
                min(clean_values),
                2,
            ),

            maximum_bps=round(
                max(clean_values),
                2,
            ),

            average_bps=round(
                mean(clean_values),
                2,
            ),

            median_bps=round(
                median(clean_values),
                2,
            ),

            p75_bps=round(
                _percentile(
                    clean_values,
                    0.75,
                ),
                2,
            ),

            p90_bps=round(
                _percentile(
                    clean_values,
                    0.90,
                ),
                2,
            ),

            p95_bps=round(
                _percentile(
                    clean_values,
                    0.95,
                ),
                2,
            ),

            p99_bps=round(
                _percentile(
                    clean_values,
                    0.99,
                ),
                2,
            ),

            latest_bps=round(
                clean_values[-1],
                2,
            ),

            first_bps=round(
                clean_values[0],
                2,
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrafficTrend:
    """
    Explainable linear trend calculated from a traffic series.
    """

    available: bool = False

    direction: TrafficDirection = (
        TrafficDirection.UNKNOWN
    )

    slope_bps_per_sample: float = 0.0

    change_bps: float = 0.0
    change_percent: float = 0.0

    confidence_percent: float = 0.0

    sample_count: int = 0

    @classmethod
    def from_values(
        cls,
        values: list[float],
    ) -> TrafficTrend:
        clean_values = [
            max(
                0.0,
                _number(value),
            )
            for value in values
        ]

        if len(clean_values) < 3:
            return cls(
                sample_count=len(
                    clean_values
                ),
            )

        slope = (
            _linear_regression_slope(
                clean_values
            )
        )

        first_value = (
            clean_values[0]
        )

        latest_value = (
            clean_values[-1]
        )

        change_bps = (
            latest_value
            - first_value
        )

        average_value = max(
            mean(clean_values),
            1.0,
        )

        normalized_slope = (
            slope / average_value
        )

        if normalized_slope > 0.02:
            direction = (
                TrafficDirection.RISING
            )
        elif normalized_slope < -0.02:
            direction = (
                TrafficDirection.FALLING
            )
        else: direction = (
                TrafficDirection.STABLE
            )

        change_percent = (
            (
                change_bps
                / abs(first_value)
                * 100.0
            )
            if abs(first_value) > 0
            else (
                100.0
                if latest_value > 0
                else 0.0
            )
        )

        confidence = _clamp(
            45.0
            + min(
                len(clean_values)
                * 2.0,
                30.0,
            )
            + min(
                abs(
                    normalized_slope
                )
                * 300.0,
                20.0,
            )
        )

        return cls(
            available=True,

            direction=direction,

            slope_bps_per_sample=
                round(
                    slope,
                    4,
                ),

            change_bps=round(
                change_bps,
                2,
            ),

            change_percent=round(
                change_percent,
                2,
            ),

            confidence_percent=
                round(
                    confidence,
                    2,
                ),

            sample_count=len(
                clean_values
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result["direction"] = (
            self.direction.value
        )

        return result


@dataclass(slots=True)
class CapacityForecast:
    """
    Capacity forecast based on the current linear traffic trend.
    """

    available: bool = False

    capacity_bps: float = 0.0
    current_bps: float = 0.0

    current_utilization_percent: float | None = None
    threshold_percent: float = 90.0
    threshold_bps: float = 0.0

    minutes_to_threshold: float | None = None

    already_above_threshold: bool = False

    reason: str | None = None

    @classmethod
    def calculate(
        cls,
        *,
        current_bps: float,
        capacity_bps: float,
        slope_bps_per_sample: float,
        sample_seconds: int,
        threshold_percent: float = 90.0,
    ) -> CapacityForecast:
        current_bps = max(
            0.0,
            _number(current_bps),
        )

        capacity_bps = max(
            0.0,
            _number(capacity_bps),
        )

        threshold_percent = (
            _clamp(
                threshold_percent,
                1.0,
                100.0,
            )
        )

        if capacity_bps <= 0:
            return cls(
                current_bps=current_bps,
                threshold_percent=
                    threshold_percent,
                reason=(
                    "Interface capacity "
                    "is unavailable"
                ),
            )

        current_utilization = (
            current_bps
            / capacity_bps
            * 100.0
        )

        threshold_bps = (
            capacity_bps
            * threshold_percent
            / 100.0
        )

        if (
            current_bps
            >= threshold_bps
        ):
            return cls(
                available=True,

                capacity_bps=round(
                    capacity_bps,
                    2,
                ),

                current_bps=round(
                    current_bps,
                    2,
                ),

                current_utilization_percent=
                    round(
                        current_utilization,
                        2,
                    ),

                threshold_percent=
                    threshold_percent,

                threshold_bps=round(
                    threshold_bps,
                    2,
                ),

                minutes_to_threshold=
                    0.0,

                already_above_threshold=
                    True,
            )

        if slope_bps_per_sample <= 0:
            return cls(
                available=True,

                capacity_bps=round(
                    capacity_bps,
                    2,
                ),

                current_bps=round(
                    current_bps,
                    2,
                ),

                current_utilization_percent=
                    round(
                        current_utilization,
                        2,
                    ),

                threshold_percent=
                    threshold_percent,

                threshold_bps=round(
                    threshold_bps,
                    2,
                ),

                reason=(
                    "Traffic is stable "
                    "or falling"
                ),
            )

        samples_needed = (
            threshold_bps
            - current_bps
        ) / slope_bps_per_sample

        seconds_needed = (
            samples_needed
            * max(
                sample_seconds,
                1,
            )
        )

        minutes_needed = max(
            0.0,
            seconds_needed / 60.0,
        )

        return cls(
            available=True,

            capacity_bps=round(
                capacity_bps,
                2,
            ),

            current_bps=round(
                current_bps,
                2,
            ),

            current_utilization_percent=
                round(
                    current_utilization,
                    2,
                ),

            threshold_percent=
                threshold_percent,

            threshold_bps=round(
                threshold_bps,
                2,
            ),

            minutes_to_threshold=
                round(
                    minutes_needed,
                    2,
                ),

            already_above_threshold=
                False,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrafficSeries:
    """
    Canonical traffic history for one router interface.
    """

    router_ip: str

    interface_name: str | None = None

    range_minutes: int = 15
    window_seconds: int = 10

    interface_speed_bps: float = 0.0

    points: list[
        TrafficPoint
    ] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.range_minutes = max(
            1,
            _integer(
                self.range_minutes,
                15,
            ),
        )

        self.window_seconds = max(
            1,
            _integer(
                self.window_seconds,
                10,
            ),
        )

        self.interface_speed_bps = max(
            0.0,
            _number(
                self.interface_speed_bps
            ),
        )

        self.points.sort(
            key=lambda point: (
                point.time
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            )
        )

    @property
    def sample_count(self) -> int:
        return len(
            self.points
        )

    @property
    def rx_values(
        self,
    ) -> list[float]:
        return [
            point.rx_bps
            for point
            in self.points
        ]

    @property
    def tx_values(
        self,
    ) -> list[float]:
        return [
            point.tx_bps
            for point
            in self.points
        ]

    @property
    def total_values(
        self,
    ) -> list[float]:
        return [
            point.total_bps
            for point
            in self.points
        ]

    @property
    def rx_statistics(
        self,
    ) -> TrafficStatistics:
        return (
            TrafficStatistics.from_values(
                self.rx_values
            )
        )

    @property
    def tx_statistics(
        self,
    ) -> TrafficStatistics:
        return (
            TrafficStatistics.from_values(
                self.tx_values
            )
        )

    @property
    def total_statistics(
        self,
    ) -> TrafficStatistics:
        return (
            TrafficStatistics.from_values(
                self.total_values
            )
        )

    @property
    def total_trend(
        self,
    ) -> TrafficTrend:
        return TrafficTrend.from_values(
            self.total_values
        )

    @property
    def rx_trend(
        self,
    ) -> TrafficTrend:
        return TrafficTrend.from_values(
            self.rx_values
        )

    @property
    def tx_trend(
        self,
    ) -> TrafficTrend:
        return TrafficTrend.from_values(
            self.tx_values
        )

    @property
    def start_time(
        self,
    ) -> datetime | None:
        if not self.points:
            return None

        return self.points[0].time

    @property
    def end_time(
        self,
    ) -> datetime | None:
        if not self.points:
            return None

        return self.points[-1].time

    @property
    def actual_duration_seconds(
        self,
    ) -> float:
        if (
            self.start_time is None
            or self.end_time is None
        ):
            return 0.0

        return max(
            0.0,
            (
                self.end_time
                - self.start_time
            ).total_seconds(),
        )

    @property
    def expected_sample_count(
        self,
    ) -> int:
        return max(
            1,
            int(
                self.range_minutes
                * 60
                / self.window_seconds
            ),
        )

    @property
    def completeness_percent(
        self,
    ) -> float:
        if (
            self.expected_sample_count
            <= 0
        ):
            return 0.0

        return round(
            _clamp(
                self.sample_count
                / self.expected_sample_count
                * 100.0
            ),
            2,
        )

    @property
    def missing_sample_count(
        self,
    ) -> int:
        return max(
            0,
            self.expected_sample_count
            - self.sample_count,
        )

    @property
    def quality(
        self,
    ) -> TrafficQuality:
        if self.sample_count == 0:
            return TrafficQuality.EMPTY

        completeness = (
            self.completeness_percent
        )

        if completeness >= 95:
            return (
                TrafficQuality.EXCELLENT
            )

        if completeness >= 80:
            return TrafficQuality.GOOD

        if completeness >= 50:
            return (
                TrafficQuality.DEGRADED
            )

        return TrafficQuality.POOR

    @property
    def current_total_bps(
        self,
    ) -> float:
        if not self.points:
            return 0.0

        return self.points[-1].total_bps

    @property
    def current_utilization_percent(
        self,
    ) -> float | None:
        if self.interface_speed_bps <= 0:
            return None

        utilization = (
            self.current_total_bps
            / self.interface_speed_bps
            * 100.0
        )

        return round(
            _clamp(
                utilization
            ),
            2,
        )

    def capacity_forecast(
        self,
        threshold_percent: float = 90.0,
    ) -> CapacityForecast:
        trend = self.total_trend

        return (
            CapacityForecast.calculate(
                current_bps=(
                    self.current_total_bps
                ),
                capacity_bps=(
                    self.interface_speed_bps
                ),
                slope_bps_per_sample=(
                    trend.slope_bps_per_sample
                ),
                sample_seconds=(
                    self.window_seconds
                ),
                threshold_percent=(
                    threshold_percent
                ),
            )
        )

    @property
    def health_flags(
        self,
    ) -> list[str]:
        flags: list[str] = []

        if self.sample_count == 0:
            flags.append(
                "traffic_data_unavailable"
            )

            return flags

        if self.quality in {
            TrafficQuality.DEGRADED,
            TrafficQuality.POOR,
        }:
            flags.append(
                "traffic_data_incomplete"
            )

        utilization = (
            self.current_utilization_percent
        )

        if (
            utilization is not None
            and utilization >= 90
        ):
            flags.append(
                "traffic_saturation"
            )
        elif (
            utilization is not None
            and utilization >= 75
        ):
            flags.append(
                "traffic_high_utilization"
            )

        trend = self.total_trend

        if (
            trend.available
            and trend.direction
            == TrafficDirection.RISING
            and trend.change_percent >= 25
        ):
            flags.append(
                "traffic_rapid_growth"
            )

        forecast = (
            self.capacity_forecast(
                90.0
            )
        )

        if (
            forecast.minutes_to_threshold
            is not None
            and forecast.minutes_to_threshold
            <= 60
        ):
            flags.append(
                "capacity_threshold_near"
            )

        return flags

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        default_ip: str = "",
        interface_speed_bps: float | None = None,
    ) -> TrafficSeries:
        interface_name = (
            _text(
                data.get("interface")
                or data.get(
                    "interface_name"
                )
                or data.get(
                    "if_descr"
                )
            )
            or None
        )

        window_seconds = max(
            1,
            _integer(
                data.get(
                    "window_seconds"
                )
                or data.get("window")
                or 10,
                10,
            ),
        )

        raw_points = data.get(
            "points",
            [],
        )

        points = [
            TrafficPoint.from_dict(
                item,
                default_interface=(
                    interface_name
                ),
                default_window_seconds=(
                    window_seconds
                ),
            )
            for item in (
                raw_points
                if isinstance(
                    raw_points,
                    list,
                )
                else []
            )
            if isinstance(
                item,
                dict,
            )
        ]

        resolved_speed = (
            interface_speed_bps
            if interface_speed_bps
            is not None
            else data.get(
                "interface_speed_bps"
            )
            or data.get(
                "speed_bps"
            )
            or 0
        )

        return cls(
            router_ip=_text(
                data.get("router_ip")
                or data.get("ip")
                or default_ip
            ),

            interface_name=(
                interface_name
            ),

            range_minutes=max(
                1,
                _integer(
                    data.get(
                        "range_minutes"
                    )
                    or data.get(
                        "minutes"
                    )
                    or 15,
                    15,
                ),
            ),

            window_seconds=(
                window_seconds
            ),

            interface_speed_bps=max(
                0.0,
                _number(
                    resolved_speed
                ),
            ),

            points=points,

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
        include_points: bool = True,
    ) -> dict[str, Any]:
        result = {
            "router_ip":
                self.router_ip,

            "interface":
                self.interface_name,

            "interface_name":
                self.interface_name,

            "range_minutes":
                self.range_minutes,

            "window_seconds":
                self.window_seconds,

            "interface_speed_bps":
                self.interface_speed_bps,

            "sample_count":
                self.sample_count,

            "expected_sample_count":
                self.expected_sample_count,

            "missing_sample_count":
                self.missing_sample_count,

            "completeness_percent":
                self.completeness_percent,

            "quality":
                self.quality.value,

            "start_time":
                _datetime_to_iso(
                    self.start_time
                ),

            "end_time":
                _datetime_to_iso(
                    self.end_time
                ),

            "actual_duration_seconds":
                round(
                    self.actual_duration_seconds,
                    2,
                ),

            "current_total_bps":
                self.current_total_bps,

            "current_utilization_percent":
                self.current_utilization_percent,

            "statistics": {
                "rx":
                    self.rx_statistics.to_dict(),
                "tx":
                    self.tx_statistics.to_dict(),
                "total":
                    self.total_statistics.to_dict(),
            },

            "trends": {
                "rx":
                    self.rx_trend.to_dict(),
                "tx":
                    self.tx_trend.to_dict(),
                "total":
                    self.total_trend.to_dict(),
            },

            "capacity_forecasts": {
                "warning_75_percent":
                    self.capacity_forecast(
                        75.0
                    ).to_dict(),

                "critical_90_percent":
                    self.capacity_forecast(
                        90.0
                    ).to_dict(),
            },

            "health_flags":
                self.health_flags,

            "metadata":
                self.metadata,
        }

        if include_points:
            result["points"] = [
                point.to_dict()
                for point
                in self.points
            ]

        return result


def normalize_traffic_points(
    points: list[
        dict[str, Any]
    ] | None,
    *,
    interface_name: str | None = None,
    window_seconds: int | None = None,
) -> list[TrafficPoint]:
    return [
        TrafficPoint.from_dict(
            item,
            default_interface=(
                interface_name
            ),
            default_window_seconds=(
                window_seconds
            ),
        )
        for item in (
            points or []
        )
        if isinstance(
            item,
            dict,
        )
    ]
