from datetime import date, datetime, time
from typing import Optional

from ninja import Schema


class UserOut(Schema):
    id: int
    email: str
    first_name: str
    last_name: str


class AuthResponse(Schema):
    token: str
    user: UserOut


class OkResponse(Schema):
    ok: bool = True


class ProjectIn(Schema):
    name: str
    color: str = "#3B82F6"


class ProjectUpdate(Schema):
    name: Optional[str] = None
    color: Optional[str] = None
    archived: Optional[bool] = None


class ProjectOut(Schema):
    id: int
    name: str
    color: str
    position: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectReorder(Schema):
    order: list[int]


class TaskIn(Schema):
    title: str
    project_id: Optional[int] = None
    time_horizon: str = "backlog"
    due_date: Optional[date] = None
    estimated_minutes: Optional[int] = None
    priority: Optional[int] = None
    description: str = ""


class TaskUpdate(Schema):
    title: Optional[str] = None
    project_id: Optional[int] = None
    time_horizon: Optional[str] = None
    due_date: Optional[date] = None
    estimated_minutes: Optional[int] = None
    priority: Optional[int] = None
    description: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


class TaskMove(Schema):
    time_horizon: str
    position: int
    project_id: Optional[int] = None


class SubtaskOut(Schema):
    id: int
    title: str
    completed: bool
    position: int


class TaskOut(Schema):
    id: int
    title: str
    description: str
    project: Optional[ProjectOut] = None
    time_horizon: str
    position: int
    due_date: Optional[date] = None
    estimated_minutes: Optional[int] = None
    priority: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    completed: bool
    completed_at: Optional[datetime] = None
    reschedule_count: int
    created_at: datetime
    updated_at: datetime
    subtasks: list[SubtaskOut] = []


class SubtaskIn(Schema):
    title: str


class SubtaskUpdate(Schema):
    title: Optional[str] = None
    completed: Optional[bool] = None
    position: Optional[int] = None


class SubtaskReorder(Schema):
    order: list[int]


class UserSettingsOut(Schema):
    scheduling_preferences: str
    morning_email_time: time
    morning_email_enabled: bool
    has_seen_tour: bool
    week_starts_on: int
    scheduling_windows: dict


class UserSettingsUpdate(Schema):
    scheduling_preferences: Optional[str] = None
    morning_email_time: Optional[time] = None
    morning_email_enabled: Optional[bool] = None
    has_seen_tour: Optional[bool] = None
    week_starts_on: Optional[int] = None
    scheduling_windows: Optional[dict] = None


class CalendarEventOut(Schema):
    id: int
    gcal_id: str
    calendar_id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str = ""
    description: str = ""


class CalendarSyncStateOut(Schema):
    id: int
    calendar_id: str
    calendar_name: str
    calendar_color: str
    is_enabled: bool
    last_synced_at: Optional[datetime] = None
    has_sync_token: bool


class SyncResultOut(Schema):
    calendar_id: str
    created: int
    updated: int
    deleted: int
    errors: list[str]
    full_sync_performed: bool


class GoogleAuthIn(Schema):
    code: str


# LLM Planning schemas
class TimeSlotOut(Schema):
    task_id: int
    start_time: str
    estimated_minutes: int


class ProposedPlanOut(Schema):
    message: str
    schedule: list[TimeSlotOut]


class TimeSlotIn(Schema):
    task_id: int
    start_time: str
    end_time: str


class CommitScheduleIn(Schema):
    slots: list[TimeSlotIn]
