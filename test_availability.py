
"""
Test Thyme's availability calculator using sample events.
No Google Calendar connection or AI model is required.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from backend.app.modules.calendar.availability import (
    TimeWindow,
    weekly_availability,
    choose_cooking_slot
)


# Define the user's time zone and requested week.
zone = ZoneInfo("America/Boise")
start_date = date(2026, 11, 30)


# Create sample calendar appointments.
busy_events = [

    # Monday: busy until 5 PM.
    TimeWindow(
        datetime(2026, 11, 30, 16, 0, tzinfo=zone),
        datetime(2026, 11, 30, 17, 0, tzinfo=zone)
    ),

    # Tuesday: busy until 5:30 PM.
    TimeWindow(
        datetime(2026, 12, 1, 16, 0, tzinfo=zone),
        datetime(2026, 12, 1, 17, 30, tzinfo=zone)
    ),

    # Thursday: unavailable during the entire cooking window.
    TimeWindow(
        datetime(2026, 12, 3, 15, 0, tzinfo=zone),
        datetime(2026, 12, 3, 19, 0, tzinfo=zone)
    ),
]


# Calculate available cooking time before dinner each day.
availability = weekly_availability(
    start_date=start_date,
    busy_windows=busy_events,
    timezone_name="America/Boise",
    cooking_start=time(16, 0),
    meal_time=time(18, 0),
    days=5,
    buffer_minutes=15
)


# Display available windows and test a 30-minute recipe.
print("\nTHYME WEEKLY AVAILABILITY")
print("=" * 50)

for day, windows in availability.items():

    print(f"\n{day.strftime('%A, %B %d')}")

    if not windows:
        print("  No available cooking time.")
        continue

    for window in windows:

        print(
            f"  Available: "
            f"{window.start.strftime('%I:%M %p')} - "
            f"{window.end.strftime('%I:%M %p')}"
            f" ({window.duration_minutes} minutes)"
        )

    # Determine whether a 30-minute recipe fits.
    slot = choose_cooking_slot(windows, 30)

    if slot:

        print(
            f"  Suggested cooking time: "
            f"{slot.start.strftime('%I:%M %p')} - "
            f"{slot.end.strftime('%I:%M %p')}"
        )

    else:
        print("  A 30-minute recipe does not fit.")
