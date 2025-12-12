from datetime import date, datetime, timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone
from openai import OpenAI
from pydantic import BaseModel

from ..models import Task, UserSettings, Project
from .calendar import get_cached_events


class TimeSlot(BaseModel):
    task_id: int
    start_time: str  # "09:00"
    estimated_minutes: int


class ProposedPlan(BaseModel):
    message: str  # brief motivational message (1-2 sentences, no task IDs)
    schedule: list[TimeSlot]


MAX_TASKS = 30


def get_tasks_for_planning(user) -> list[Task]:
    """Get tasks relevant for daily planning, capped at MAX_TASKS.

    Priority order:
    1. Overdue and this week's tasks first
    2. If under cap, fill with later tasks
    """
    today = date.today()
    end_of_week = today + timedelta(days=(6 - today.weekday()))  # Sunday

    # First: get overdue + this week tasks
    priority_tasks = list(Task.objects.filter(
        user=user,
        completed=False,
        due_date__lte=end_of_week,
    ).select_related("project").order_by("due_date", "-priority", "position")[:MAX_TASKS])

    # If under cap, fill with later tasks
    if len(priority_tasks) < MAX_TASKS:
        remaining = MAX_TASKS - len(priority_tasks)
        priority_task_ids = [t.id for t in priority_tasks]

        later_tasks = list(Task.objects.filter(
            user=user,
            completed=False,
        ).exclude(
            id__in=priority_task_ids
        ).filter(
            due_date__gt=end_of_week
        ).select_related("project").order_by("due_date", "-priority", "position")[:remaining])

        priority_tasks.extend(later_tasks)

    return priority_tasks


def get_calendar_events_for_planning(user) -> list:
    """Get calendar events for the next 3 days."""
    now = timezone.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_range = (now + timedelta(days=3)).replace(hour=23, minute=59, second=59, microsecond=999999)

    return get_cached_events(user, start_of_day, end_of_range)


def format_tasks_for_prompt(tasks: list[Task]) -> str:
    """Format tasks as text for the LLM prompt."""
    lines = []
    for task in tasks:
        parts = [f"- ID:{task.id} \"{task.title}\""]
        if task.project:
            parts.append(f"[{task.project.name}]")
        if task.due_date:
            parts.append(f"due:{task.due_date}")
        if task.estimated_minutes:
            parts.append(f"~{task.estimated_minutes}min")
        else:
            parts.append("(no estimate)")
        if task.priority:
            priority_names = {1: "high", 2: "medium", 3: "low"}
            parts.append(f"priority:{priority_names.get(task.priority, task.priority)}")
        if task.reschedule_count > 0:
            parts.append(f"rescheduled:{task.reschedule_count}x")
        lines.append(" ".join(parts))
    return "\n".join(lines) if lines else "(no tasks)"


def format_calendar_for_prompt(events: list) -> str:
    """Format calendar events as text for the LLM prompt, grouped by day."""
    if not events:
        return "(no calendar events)"

    # Group events by date
    events_by_date: dict[date, list] = {}
    for event in events:
        event_date = event.start.date()
        if event_date not in events_by_date:
            events_by_date[event_date] = []
        events_by_date[event_date].append(event)

    lines = []
    today = date.today()
    for event_date in sorted(events_by_date.keys()):
        # Label the day
        if event_date == today:
            day_label = "Today"
        elif event_date == today + timedelta(days=1):
            day_label = "Tomorrow"
        else:
            day_label = event_date.strftime("%A")  # e.g., "Saturday"

        lines.append(f"{day_label}:")
        for event in events_by_date[event_date]:
            start = event.start.strftime("%H:%M")
            end = event.end.strftime("%H:%M")
            lines.append(f"  - {start}-{end}: {event.title}")

    return "\n".join(lines)


DEFAULT_TASK_DURATION = 30  # minutes for tasks without estimates
DEFAULT_WINDOWS = [
    {"start": "09:00", "end": "12:00"},
    {"start": "14:00", "end": "18:00"},
]


def get_scheduling_windows_for_day(user, day_name: str) -> list[tuple[int, int]]:
    """Get scheduling windows for a specific day as list of (start_mins, end_mins) tuples."""
    try:
        user_settings = UserSettings.objects.get(user=user)
        windows = user_settings.scheduling_windows or {}
    except UserSettings.DoesNotExist:
        windows = {}

    day_windows = windows.get(day_name.lower(), DEFAULT_WINDOWS)

    result = []
    for w in day_windows:
        start_h, start_m = map(int, w["start"].split(":"))
        end_h, end_m = map(int, w["end"].split(":"))
        result.append((start_h * 60 + start_m, end_h * 60 + end_m))

    return sorted(result)


def generate_deterministic_plan(user) -> ProposedPlan:
    """Generate a daily plan using deterministic scheduling."""
    today = date.today()
    day_name = today.strftime("%A").lower()

    # Get user's scheduling windows for today
    scheduling_windows = get_scheduling_windows_for_day(user, day_name)

    # Get tasks and calendar
    tasks = get_tasks_for_planning(user)
    calendar_events = get_calendar_events_for_planning(user)

    # Filter to today's calendar events only
    today_events = [
        e for e in calendar_events
        if e.start.date() == today and not e.all_day
    ]

    # Build list of busy periods (start_minutes, end_minutes from midnight)
    busy_periods = []
    for event in today_events:
        start_mins = event.start.hour * 60 + event.start.minute
        end_mins = event.end.hour * 60 + event.end.minute
        busy_periods.append((start_mins, end_mins))
    busy_periods.sort()

    # Score and sort tasks for scheduling
    def task_score(task: Task) -> tuple:
        # Lower score = higher priority
        is_overdue = task.due_date and task.due_date < today
        is_due_today = task.due_date == today
        priority = task.priority or 99
        reschedules = task.reschedule_count
        return (
            0 if is_overdue else 1,
            priority,
            -reschedules,  # more reschedules = schedule sooner
            0 if is_due_today else 1,
            task.position,
        )

    sorted_tasks = sorted(tasks, key=task_score)

    # Build list of available slots from scheduling windows minus busy periods
    available_slots: list[tuple[int, int]] = []
    for window_start, window_end in scheduling_windows:
        slots = [(window_start, window_end)]
        for busy_start, busy_end in busy_periods:
            new_slots = []
            for slot_start, slot_end in slots:
                if busy_end <= slot_start or busy_start >= slot_end:
                    new_slots.append((slot_start, slot_end))
                else:
                    if slot_start < busy_start:
                        new_slots.append((slot_start, busy_start))
                    if busy_end < slot_end:
                        new_slots.append((busy_end, slot_end))
            slots = new_slots
        available_slots.extend(slots)

    available_slots.sort()

    # Schedule tasks into available slots
    schedule: list[TimeSlot] = []
    slot_idx = 0
    current_pos = available_slots[0][0] if available_slots else 0

    for task in sorted_tasks:
        if slot_idx >= len(available_slots):
            break

        duration = task.estimated_minutes or DEFAULT_TASK_DURATION

        # Find slot that fits this task
        while slot_idx < len(available_slots):
            slot_start, slot_end = available_slots[slot_idx]
            if current_pos < slot_start:
                current_pos = slot_start

            if current_pos + duration <= slot_end:
                schedule.append(TimeSlot(
                    task_id=task.id,
                    start_time=f"{current_pos // 60:02d}:{current_pos % 60:02d}",
                    estimated_minutes=duration,
                ))
                current_pos += duration
                break
            else:
                slot_idx += 1
                if slot_idx < len(available_slots):
                    current_pos = available_slots[slot_idx][0]

    # Generate message
    overdue_count = sum(1 for t in sorted_tasks if t.due_date and t.due_date < today)
    high_priority_count = sum(1 for t in sorted_tasks if t.priority == 1)

    if overdue_count > 0:
        message = f"You have {overdue_count} overdue task{'s' if overdue_count > 1 else ''} to tackle today. Let's get through them!"
    elif high_priority_count > 0:
        message = f"You have {high_priority_count} high-priority task{'s' if high_priority_count > 1 else ''} today. Focus on what matters most."
    elif len(schedule) > 5:
        message = "Busy day ahead! Take it one task at a time."
    elif len(schedule) > 0:
        message = "Here's your plan for today. You've got this!"
    else:
        message = "Looks like a light day. Great time to get ahead on upcoming tasks."

    return ProposedPlan(message=message, schedule=schedule)


def generate_daily_plan(user) -> ProposedPlan:
    """Generate a daily plan using OpenAI."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Gather data
    tasks = get_tasks_for_planning(user)
    calendar_events = get_calendar_events_for_planning(user)

    # Get user preferences
    try:
        user_settings = UserSettings.objects.get(user=user)
        preferences = user_settings.scheduling_preferences or "No specific preferences set."
    except UserSettings.DoesNotExist:
        preferences = "No specific preferences set."

    # Build prompt
    tasks_text = format_tasks_for_prompt(tasks)
    calendar_text = format_calendar_for_prompt(calendar_events)
    today_str = date.today().strftime("%A, %B %d")

    system_prompt = """You are a friendly productivity coach. Schedule tasks into time slots for today.

Rules:
- Prioritize overdue and high-priority tasks
- Estimate duration for tasks without estimates
- Don't overlap with calendar events
- Be realistic about what fits

For the message: Write 1-2 friendly, motivational sentences. Reference task names naturally (not IDs). Keep it warm and encouraging."""

    user_prompt = f"""Today: {today_str}
Preferences: {preferences}

Calendar:
{calendar_text}

Tasks:
{tasks_text}

Create a schedule for today."""

    response = client.responses.parse(
        model="gpt-5-nano-2025-08-07",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text_format=ProposedPlan,
    )

    return response.output_parsed
