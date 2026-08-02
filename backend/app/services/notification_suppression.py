from __future__ import annotations

from datetime import (
    datetime,
    time,
    timedelta,
)
from typing import Any
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from app.models.notification import (
    NotificationSuppression,
    NotificationSuppressionKind,
)
from app.models.notification_suppression_engine import (
    NotificationSuppressionContext,
    NotificationSuppressionDecision,
    NotificationSuppressionDecisionCode,
    QuietHoursWindow,
)
from app.services.notification_store import (
    NotificationStore,
)


def _normalize_strings(
    value: Any,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        values = [value]
    elif isinstance(
        value,
        (list, tuple, set),
    ):
        values = list(value)
    else:
        raise ValueError(
            "Suppression metadata value must "
            "be a string or sequence"
        )

    normalized: list[str] = []

    for item in values:
        text = str(item).strip().lower()

        if text and text not in normalized:
            normalized.append(text)

    return tuple(normalized)


def _parse_clock(
    value: Any,
    *,
    field_name: str,
) -> time:
    if isinstance(value, time):
        return value.replace(
            tzinfo=None
        )

    text = str(value).strip()

    formats = (
        "%H:%M",
        "%H:%M:%S",
    )

    for format_value in formats:
        try:
            return datetime.strptime(
                text,
                format_value,
            ).time()
        except ValueError:
            continue

    raise ValueError(
        f"Invalid {field_name}: {value}"
    )


def _parse_weekdays(
    value: Any,
) -> tuple[int, ...]:
    if value is None:
        return (
            0,
            1,
            2,
            3,
            4,
            5,
            6,
        )

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        raise ValueError(
            "Quiet-hours weekdays must be "
            "a sequence"
        )

    name_map = {
        "monday": 0,
        "mon": 0,
        "tuesday": 1,
        "tue": 1,
        "wednesday": 2,
        "wed": 2,
        "thursday": 3,
        "thu": 3,
        "friday": 4,
        "fri": 4,
        "saturday": 5,
        "sat": 5,
        "sunday": 6,
        "sun": 6,
    }

    result: list[int] = []

    for item in value:
        if isinstance(item, int):
            day = item
        else:
            normalized = str(
                item
            ).strip().lower()

            if normalized not in name_map:
                raise ValueError(
                    "Invalid quiet-hours "
                    f"weekday: {item}"
                )

            day = name_map[normalized]

        if day < 0 or day > 6:
            raise ValueError(
                "Quiet-hours weekday must be "
                "between 0 and 6"
            )

        if day not in result:
            result.append(day)

    return tuple(result)


class NotificationSuppressionEngine:
    def __init__(
        self,
        store: NotificationStore,
    ) -> None:
        self._store = store

    @staticmethod
    def _scope_matches(
        configured_values: tuple[str, ...],
        actual_value: str | None,
    ) -> bool:
        if not configured_values:
            return True

        if actual_value is None:
            return False

        normalized_actual = (
            str(actual_value)
            .strip()
            .lower()
        )

        configured = {
            str(item).strip().lower()
            for item in configured_values
        }

        return (
            "*"
            in configured
            or normalized_actual in configured
        )

    def _matches_context(
        self,
        suppression: NotificationSuppression,
        context: NotificationSuppressionContext,
    ) -> bool:
        return all(
            (
                self._scope_matches(
                    suppression.event_types,
                    context.event_type,
                ),
                self._scope_matches(
                    suppression.site_ids,
                    context.site_id,
                ),
                self._scope_matches(
                    suppression.device_ids,
                    context.device_id,
                ),
            )
        )

    @staticmethod
    def _bypass_reason(
        suppression: NotificationSuppression,
        context: NotificationSuppressionContext,
    ) -> str | None:
        metadata = suppression.metadata

        if context.force:
            return (
                "Suppression bypassed by "
                "forced notification"
            )

        bypass_severities = (
            _normalize_strings(
                metadata.get(
                    "bypass_severities"
                )
            )
        )

        if (
            context.severity
            and context.severity.strip().lower()
            in bypass_severities
        ):
            return (
                "Suppression bypassed for "
                f"severity: {context.severity}"
            )

        bypass_types = _normalize_strings(
            metadata.get(
                "bypass_notification_types"
            )
        )

        notification_type = (
            context.notification_type_value
        )

        if (
            notification_type
            and notification_type
            in bypass_types
        ):
            return (
                "Suppression bypassed for "
                "notification type: "
                f"{notification_type}"
            )

        return None

    @staticmethod
    def _quiet_hours_window(
        suppression: NotificationSuppression,
    ) -> QuietHoursWindow:
        metadata = suppression.metadata

        start_value = metadata.get(
            "start_time",
            metadata.get(
                "quiet_start",
                "22:00",
            ),
        )

        end_value = metadata.get(
            "end_time",
            metadata.get(
                "quiet_end",
                "06:00",
            ),
        )

        timezone_name = str(
            metadata.get(
                "timezone",
                "UTC",
            )
        ).strip()

        if not timezone_name:
            raise ValueError(
                "Quiet-hours timezone must "
                "not be empty"
            )

        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "Unknown quiet-hours timezone: "
                f"{timezone_name}"
            ) from exc

        return QuietHoursWindow(
            start_time=_parse_clock(
                start_value,
                field_name=(
                    "quiet-hours start time"
                ),
            ),
            end_time=_parse_clock(
                end_value,
                field_name=(
                    "quiet-hours end time"
                ),
            ),
            timezone_name=timezone_name,
            weekdays=_parse_weekdays(
                metadata.get("weekdays")
            ),
        )

    @staticmethod
    def _inside_quiet_hours(
        window: QuietHoursWindow,
        evaluated_at: datetime,
    ) -> bool:
        local_datetime = (
            evaluated_at.astimezone(
                ZoneInfo(
                    window.timezone_name
                )
            )
        )

        local_time = local_datetime.time().replace(
            tzinfo=None
        )

        weekday = local_datetime.weekday()

        if window.full_day:
            return weekday in window.weekdays

        if not window.overnight:
            return (
                weekday in window.weekdays
                and window.start_time
                <= local_time
                < window.end_time
            )

        if local_time >= window.start_time:
            return weekday in window.weekdays

        if local_time < window.end_time:
            previous_weekday = (
                local_datetime
                - timedelta(days=1)
            ).weekday()

            return (
                previous_weekday
                in window.weekdays
            )

        return False

    def evaluate(
        self,
        context: NotificationSuppressionContext,
    ) -> NotificationSuppressionDecision:
        suppressions = (
            self._store
            .list_active_suppressions(
                at=context.evaluated_at
            )
        )

        for suppression in suppressions:
            if not self._matches_context(
                suppression,
                context,
            ):
                continue

            bypass_reason = self._bypass_reason(
                suppression,
                context,
            )

            if bypass_reason is not None:
                return NotificationSuppressionDecision(
                    code=(
                        NotificationSuppressionDecisionCode
                        .BYPASSED
                    ),
                    context=context,
                    suppressed=False,
                    suppression=suppression,
                    reason=bypass_reason,
                )

            quiet_window = None

            if (
                suppression.kind
                is NotificationSuppressionKind
                .QUIET_HOURS
            ):
                quiet_window = (
                    self._quiet_hours_window(
                        suppression
                    )
                )

                if not self._inside_quiet_hours(
                    quiet_window,
                    context.evaluated_at,
                ):
                    continue

            return NotificationSuppressionDecision(
                code=(
                    NotificationSuppressionDecisionCode
                    .SUPPRESSED
                ),
                context=context,
                suppressed=True,
                suppression=suppression,
                quiet_hours_window=quiet_window,
                reason=(
                    suppression.reason
                    or (
                        "Notification suppressed "
                        f"by {suppression.kind.value}"
                    )
                ),
            )

        return NotificationSuppressionDecision(
            code=(
                NotificationSuppressionDecisionCode
                .ALLOWED
            ),
            context=context,
            suppressed=False,
            reason=(
                "No active suppression matched"
            ),
        )

    def is_suppressed(
        self,
        context: NotificationSuppressionContext,
    ) -> bool:
        return self.evaluate(
            context
        ).suppressed


def evaluate_notification_suppression(
    store: NotificationStore,
    context: NotificationSuppressionContext,
) -> NotificationSuppressionDecision:
    return NotificationSuppressionEngine(
        store
    ).evaluate(context)
