from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import models


def get_sunday_of_week(d: date) -> date:
    """Get the Sunday of the week containing date d (Monday=0, Sunday=6)."""
    days_until_sunday = 6 - d.weekday()
    return d + timedelta(days=days_until_sunday)


def get_end_of_month(d: date) -> date:
    """Get the last day of the month containing date d."""
    if d.month == 12:
        return d.replace(day=31)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)


class UserSettings(models.Model):
    class WeekDay(models.IntegerChoices):
        SUNDAY = 0, "Sunday"
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")

    scheduling_preferences = models.TextField(blank=True)
    morning_email_time = models.TimeField(default="06:00")
    morning_email_enabled = models.BooleanField(default=True)
    has_seen_tour = models.BooleanField(default=False)
    week_starts_on = models.IntegerField(
        choices=WeekDay.choices, default=WeekDay.MONDAY
    )

    scheduling_windows = models.JSONField(default=dict)

    google_refresh_token = models.TextField(blank=True)
    synced_calendar_ids = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.user.email}"


class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    color = models.CharField(max_length=7, default="#3B82F6")
    archived = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.name


class Task(models.Model):
    class TimeHorizon(models.TextChoices):
        TODAY = "today", "Today"
        THIS_WEEK = "this_week", "This Week"
        NEXT_WEEK = "next_week", "Next Week"
        LATER = "later", "Later"
        BACKLOG = "backlog", "Backlog"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    position = models.IntegerField(default=0)

    due_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.IntegerField(null=True, blank=True)
    priority = models.IntegerField(null=True, blank=True)

    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    gcal_event_id = models.CharField(max_length=200, blank=True)

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    reschedule_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.title

    @property
    def time_horizon(self) -> str:
        """Compute time horizon from due_date."""
        if self.due_date is None:
            return self.TimeHorizon.BACKLOG

        today = date.today()
        this_sunday = get_sunday_of_week(today)
        next_sunday = this_sunday + timedelta(days=7)

        if self.due_date <= today:
            return self.TimeHorizon.TODAY
        elif self.due_date <= this_sunday:
            return self.TimeHorizon.THIS_WEEK
        elif self.due_date <= next_sunday:
            return self.TimeHorizon.NEXT_WEEK
        else:
            return self.TimeHorizon.LATER

    @staticmethod
    def due_date_for_horizon(horizon: str) -> date | None:
        """Convert a time horizon column to a due_date."""
        today = date.today()

        if horizon == Task.TimeHorizon.TODAY:
            return today
        elif horizon == Task.TimeHorizon.THIS_WEEK:
            return get_sunday_of_week(today)
        elif horizon == Task.TimeHorizon.NEXT_WEEK:
            return get_sunday_of_week(today) + timedelta(days=7)
        elif horizon == Task.TimeHorizon.LATER:
            return get_end_of_month(today)
        else:  # BACKLOG
            return None


class Subtask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=500)
    completed = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.title


class CalendarSyncState(models.Model):
    """Tracks sync state for each Google Calendar being synced for a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calendar_sync_states")
    calendar_id = models.CharField(max_length=200)
    calendar_name = models.CharField(max_length=200, blank=True)
    calendar_color = models.CharField(max_length=20, blank=True)

    sync_token = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "calendar_id"]

    def __str__(self):
        return f"{self.calendar_name or self.calendar_id} ({self.user.email})"


class CalendarEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calendar_events")
    gcal_id = models.CharField(max_length=200)
    calendar_id = models.CharField(max_length=200)
    title = models.CharField(max_length=500)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)

    location = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="confirmed")
    etag = models.CharField(max_length=100, blank=True)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "calendar_id", "gcal_id"]
        indexes = [
            models.Index(fields=["user", "start", "end"]),
            models.Index(fields=["user", "calendar_id"]),
        ]

    def __str__(self):
        return self.title
