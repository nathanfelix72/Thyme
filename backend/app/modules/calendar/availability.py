
"""
Thyme Calendar Availability Calculator

Calculates available cooking windows based on the user's
calendar events, preferred meal times, and scheduling preferences.

This module operates independently of Google Calendar
and the AI model.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


# ==================================================
# TIME WINDOW DATA STRUCTURE
# ==================================================
# Represent both busy calendar intervals and available
# cooking windows using the same structure.

@dataclass(frozen=True)
class TimeWindow:

    start: datetime
    end: datetime

    # Validate that the times are usable.
    def __post_init__(self):

        if (
            self.start.utcoffset() is None
            or self.end.utcoffset() is None
        ):
            raise ValueError("Time windows must include a time zone.")

        if (
            self.end.astimezone(timezone.utc)
            <= self.start.astimezone(timezone.utc)
        ):
            raise ValueError("End time must be after start time.")

    # Calculate the length of the window in minutes.
    @property
    def duration_minutes(self) -> int:

        elapsed = (
            self.end.astimezone(timezone.utc)
            - self.start.astimezone(timezone.utc)
        )

        return int(elapsed.total_seconds() // 60)


# ==================================================
# FIND AVAILABLE TIME WINDOWS
# ==================================================
# Examine a requested cooking period and remove any
# time occupied by existing calendar events.

def find_free_windows(
    window: TimeWindow,
    busy_windows: list[TimeWindow],
    buffer_minutes: int = 0,
    minimum_minutes: int = 1,
) -> list[TimeWindow]:

    if buffer_minutes < 0 or minimum_minutes < 1:
        raise ValueError("Invalid buffer or minimum duration.")

    # Use UTC internally to avoid time zone calculation issues.
    start = window.start.astimezone(timezone.utc)
    end = window.end.astimezone(timezone.utc)

    buffer = timedelta(minutes=buffer_minutes)
    local_zone = window.start.tzinfo

    blocked = []

    # Add transition time before and after existing events.
    # Only keep portions that overlap our cooking window.
    for event in busy_windows:

        busy_start = max(
            start,
            event.start.astimezone(timezone.utc) - buffer
        )

        busy_end = min(
            end,
            event.end.astimezone(timezone.utc) + buffer
        )

        if busy_start < busy_end:
            blocked.append((busy_start, busy_end))

    # Sort events chronologically.
    blocked.sort()

    free = []
    cursor = start

    # Find gaps between busy events.
    # Overlapping events are handled without double-counting.
    for busy_start, busy_end in blocked:

        if cursor < busy_start:

            free.append(
                TimeWindow(
                    cursor.astimezone(local_zone),
                    busy_start.astimezone(local_zone)
                )
            )

        cursor = max(cursor, busy_end)

    # Include any available time after the last event.
    if cursor < end:

        free.append(
            TimeWindow(
                cursor.astimezone(local_zone),
                end.astimezone(local_zone)
            )
        )

    # Remove windows that are too short to be useful.
    return [
        gap for gap in free
        if gap.duration_minutes >= minimum_minutes
    ]


# ==================================================
# CALCULATE WEEKLY AVAILABILITY
# ==================================================
# Repeat the availability calculation for each day.
# Default settings assume dinner at 6 PM, but the
# agent can customize these based on user requests.

def weekly_availability(
    start_date: date,
    busy_windows: list[TimeWindow],
    timezone_name: str,
    cooking_start: time = time(16, 0),
    meal_time: time = time(18, 0),
    days: int = 7,
    buffer_minutes: int = 0,
    minimum_minutes: int = 1,
) -> dict[date, list[TimeWindow]]:

    # Validate the requested date range.
    if not 1 <= days <= 31:
        raise ValueError("Choose between 1 and 31 days.")

    if (
        cooking_start.tzinfo is not None
        or meal_time.tzinfo is not None
    ):
        raise ValueError("Use local clock times without a time zone.")

    if cooking_start >= meal_time:
        raise ValueError("Cooking must start before the meal on the same day.")

    # Convert the user's time zone into a Python object.
    zone = ZoneInfo(timezone_name)

    result = {}

    # Calculate availability for each requested day.
    for offset in range(days):

        day = start_date + timedelta(days=offset)

        # Create the cooking period for this specific date.
        window = TimeWindow(
            datetime.combine(day, cooking_start, tzinfo=zone),
            datetime.combine(day, meal_time, tzinfo=zone),
        )

        # Find uninterrupted periods available for cooking.
        result[day] = find_free_windows(
            window,
            busy_windows,
            buffer_minutes,
            minimum_minutes
        )

    return result


# ==================================================
# FIND A COOKING SLOT FOR A RECIPE
# ==================================================
# Given a recipe's duration, select the latest
# uninterrupted cooking slot that can accommodate it.
# This helps keep meals close to the desired eating time.

def choose_cooking_slot(
    free_windows: list[TimeWindow],
    duration_minutes: int
) -> TimeWindow | None:

    if duration_minutes <= 0:
        raise ValueError("Recipe duration must be positive.")

    duration = timedelta(minutes=duration_minutes)

    # Examine the latest available windows first.
    sorted_windows = sorted(
        free_windows,
        key=lambda w: w.end.astimezone(timezone.utc),
        reverse=True
    )

    for window in sorted_windows:

        if window.duration_minutes >= duration_minutes:

            start = (
                window.end.astimezone(timezone.utc)
                - duration
            )

            return TimeWindow(
                start.astimezone(window.start.tzinfo),
                window.end
            )

    # No available window is long enough for this recipe.
    return None
