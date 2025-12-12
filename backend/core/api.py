from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import NinjaAPI, Router, Schema
from ninja.security import HttpBearer

from .models import CalendarEvent, CalendarSyncState, Project, Subtask, Task, UserSettings, get_sunday_of_week
from .schemas import (
    CalendarEventOut,
    CalendarSyncStateOut,
    CommitScheduleIn,
    OkResponse,
    ProjectIn,
    ProjectOut,
    ProjectReorder,
    ProjectUpdate,
    ProposedPlanOut,
    SubtaskIn,
    SubtaskOut,
    SubtaskReorder,
    SubtaskUpdate,
    SyncResultOut,
    TaskIn,
    TaskMove,
    TaskOut,
    TaskUpdate,
    UserOut,
    UserSettingsOut,
    UserSettingsUpdate,
)
from .services.calendar import (
    fetch_calendar_list,
    fetch_events,
    get_cached_events,
    sync_all_calendars,
)
from .services.llm import generate_daily_plan

api = NinjaAPI(title="Timeboard API", version="1.0.0")


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if request.user.is_authenticated:
            return request.user
        return None


class SessionAuth:
    def __call__(self, request):
        if request.user.is_authenticated:
            return request.user
        return None


session_auth = SessionAuth()


HORIZON_ORDER = {
    Task.TimeHorizon.TODAY: 0,
    Task.TimeHorizon.THIS_WEEK: 1,
    Task.TimeHorizon.NEXT_WEEK: 2,
    Task.TimeHorizon.LATER: 3,
    Task.TimeHorizon.BACKLOG: 4,
}


def is_postponed(old_horizon: str, new_horizon: str) -> bool:
    """Return True if new_horizon is later than old_horizon."""
    return HORIZON_ORDER.get(new_horizon, 0) > HORIZON_ORDER.get(old_horizon, 0)


def get_horizon_date_filter(horizon: str) -> Q:
    """Get a Q filter for tasks in a given time horizon based on due_date."""
    today = date.today()
    this_sunday = get_sunday_of_week(today)
    next_sunday = this_sunday + timedelta(days=7)

    if horizon == Task.TimeHorizon.BACKLOG:
        return Q(due_date__isnull=True)
    elif horizon == Task.TimeHorizon.TODAY:
        return Q(due_date__lte=today)
    elif horizon == Task.TimeHorizon.THIS_WEEK:
        return Q(due_date__gt=today, due_date__lte=this_sunday)
    elif horizon == Task.TimeHorizon.NEXT_WEEK:
        return Q(due_date__gt=this_sunday, due_date__lte=next_sunday)
    else:  # LATER
        return Q(due_date__gt=next_sunday)


auth_router = Router(tags=["auth"])
projects_router = Router(tags=["projects"], auth=session_auth)
tasks_router = Router(tags=["tasks"], auth=session_auth)
subtasks_router = Router(tags=["subtasks"], auth=session_auth)
settings_router = Router(tags=["settings"], auth=session_auth)
calendar_router = Router(tags=["calendar"], auth=session_auth)
llm_router = Router(tags=["llm"], auth=session_auth)


class AuthStatusOut(Schema):
    authenticated: bool
    user: UserOut | None = None
    google_connected: bool = False


@auth_router.get("/me", response=UserOut)
def get_current_user(request):
    user = request.user
    if not user.is_authenticated:
        return api.create_response(request, {"detail": "Not authenticated"}, status=401)
    return user


@auth_router.get("/status", response=AuthStatusOut)
def get_auth_status(request):
    """Get authentication status including Google connection."""
    from allauth.socialaccount.models import SocialAccount

    user = request.user
    if not user.is_authenticated:
        return {"authenticated": False, "user": None, "google_connected": False}

    google_connected = SocialAccount.objects.filter(user=user, provider="google").exists()
    return {
        "authenticated": True,
        "user": user,
        "google_connected": google_connected,
    }


@auth_router.get("/google-login-url")
def get_google_login_url(request):
    """Get the URL to initiate Google OAuth login."""
    return {"url": "/accounts/google/login/"}


@auth_router.post("/logout", response=OkResponse)
def logout(request):
    from django.contrib.auth import logout
    logout(request)
    return {"ok": True}


@projects_router.get("/", response=list[ProjectOut])
def list_projects(request):
    return Project.objects.filter(user=request.user)


@projects_router.post("/", response=ProjectOut)
def create_project(request, data: ProjectIn):
    max_position = Project.objects.filter(user=request.user).count()
    project = Project.objects.create(
        user=request.user,
        name=data.name,
        color=data.color,
        position=max_position,
    )
    return project


@projects_router.patch("/{project_id}", response=ProjectOut)
def update_project(request, project_id: int, data: ProjectUpdate):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.save()
    return project


@projects_router.delete("/{project_id}", response=OkResponse)
def delete_project(request, project_id: int):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    project.delete()
    return {"ok": True}


@projects_router.patch("/reorder", response=OkResponse)
def reorder_projects(request, data: ProjectReorder):
    with transaction.atomic():
        for idx, project_id in enumerate(data.order):
            Project.objects.filter(id=project_id, user=request.user).update(position=idx)
    return {"ok": True}


@tasks_router.get("/", response=list[TaskOut])
def list_tasks(
    request,
    project_id: int | None = None,
    time_horizon: str | None = None,
    completed: bool | None = None,
):
    qs = Task.objects.filter(user=request.user).select_related("project").prefetch_related("subtasks")
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    if time_horizon is not None:
        qs = qs.filter(get_horizon_date_filter(time_horizon))
    if completed is not None:
        qs = qs.filter(completed=completed)
    return qs


@tasks_router.post("/", response=TaskOut)
def create_task(request, data: TaskIn):
    # If due_date provided, use it; otherwise derive from time_horizon
    due_date = data.due_date
    if due_date is None and data.time_horizon:
        due_date = Task.due_date_for_horizon(data.time_horizon)

    # Count tasks in the target horizon for position
    horizon_filter = get_horizon_date_filter(data.time_horizon)
    max_position = Task.objects.filter(user=request.user).filter(horizon_filter).count()

    task = Task.objects.create(
        user=request.user,
        title=data.title,
        description=data.description,
        project_id=data.project_id,
        due_date=due_date,
        estimated_minutes=data.estimated_minutes,
        position=max_position,
    )
    return Task.objects.select_related("project").prefetch_related("subtasks").get(id=task.id)


@tasks_router.patch("/{task_id}", response=TaskOut)
def update_task(request, task_id: int, data: TaskUpdate):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    update_data = data.model_dump(exclude_unset=True)

    old_horizon = task.time_horizon

    # If time_horizon is being set, convert to due_date
    if "time_horizon" in update_data:
        horizon = update_data.pop("time_horizon")
        update_data["due_date"] = Task.due_date_for_horizon(horizon)

    for field, value in update_data.items():
        setattr(task, field, value)

    # Check if task was postponed
    new_horizon = task.time_horizon
    if is_postponed(old_horizon, new_horizon):
        task.reschedule_count += 1

    task.save()
    return Task.objects.select_related("project").prefetch_related("subtasks").get(id=task.id)


@tasks_router.delete("/{task_id}", response=OkResponse)
def delete_task(request, task_id: int):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    task.delete()
    return {"ok": True}


@tasks_router.patch("/{task_id}/move", response=OkResponse)
def move_task(request, task_id: int, data: TaskMove):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    with transaction.atomic():
        old_horizon = task.time_horizon
        new_horizon = data.time_horizon
        new_position = data.position

        # Update positions in old horizon
        if old_horizon != new_horizon:
            old_filter = get_horizon_date_filter(old_horizon)
            Task.objects.filter(user=request.user).filter(old_filter).filter(
                position__gt=task.position,
            ).update(position=models.F("position") - 1)

        # Update positions in new horizon
        new_filter = get_horizon_date_filter(new_horizon)
        Task.objects.filter(user=request.user).filter(new_filter).filter(
            position__gte=new_position,
        ).exclude(id=task_id).update(position=models.F("position") + 1)

        # Update task's due_date based on target horizon
        task.due_date = Task.due_date_for_horizon(new_horizon)
        task.position = new_position
        if data.project_id is not None:
            task.project_id = data.project_id

        # Increment reschedule count if postponed
        if is_postponed(old_horizon, new_horizon):
            task.reschedule_count += 1

        task.save()

    return {"ok": True}


@tasks_router.post("/{task_id}/complete", response=TaskOut)
def complete_task(request, task_id: int):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    task.completed = True
    task.completed_at = timezone.now()
    task.save()
    return Task.objects.select_related("project").prefetch_related("subtasks").get(id=task.id)


@tasks_router.post("/{task_id}/uncomplete", response=TaskOut)
def uncomplete_task(request, task_id: int):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    task.completed = False
    task.completed_at = None
    task.save()
    return Task.objects.select_related("project").prefetch_related("subtasks").get(id=task.id)


@tasks_router.post("/{task_id}/subtasks", response=SubtaskOut)
def create_subtask(request, task_id: int, data: SubtaskIn):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    max_position = task.subtasks.count()
    subtask = Subtask.objects.create(
        task=task,
        title=data.title,
        position=max_position,
    )
    return subtask


@subtasks_router.patch("/{subtask_id}", response=SubtaskOut)
def update_subtask(request, subtask_id: int, data: SubtaskUpdate):
    subtask = get_object_or_404(Subtask, id=subtask_id, task__user=request.user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(subtask, field, value)
    subtask.save()
    return subtask


@subtasks_router.delete("/{subtask_id}", response=OkResponse)
def delete_subtask(request, subtask_id: int):
    subtask = get_object_or_404(Subtask, id=subtask_id, task__user=request.user)
    subtask.delete()
    return {"ok": True}


@subtasks_router.post("/{subtask_id}/toggle", response=SubtaskOut)
def toggle_subtask(request, subtask_id: int):
    subtask = get_object_or_404(Subtask, id=subtask_id, task__user=request.user)
    subtask.completed = not subtask.completed
    subtask.save()
    return subtask


@tasks_router.patch("/{task_id}/subtasks/reorder", response=OkResponse)
def reorder_subtasks(request, task_id: int, data: SubtaskReorder):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    with transaction.atomic():
        for idx, subtask_id in enumerate(data.order):
            Subtask.objects.filter(id=subtask_id, task=task).update(position=idx)
    return {"ok": True}


@settings_router.get("/", response=UserSettingsOut)
def get_settings(request):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    return settings_obj


@settings_router.patch("/", response=UserSettingsOut)
def update_settings(request, data: UserSettingsUpdate):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings_obj, field, value)
    settings_obj.save()
    return settings_obj


class GoogleCalendarOut(Schema):
    id: str
    name: str
    color: str
    primary: bool


class GoogleEventOut(Schema):
    id: str
    calendar_id: str
    title: str
    start: str
    end: str
    all_day: bool
    location: str | None = None
    description: str | None = None
    color: str | None = None


@calendar_router.get("/calendars", response=list[GoogleCalendarOut])
def list_google_calendars(request):
    """List all Google calendars the user has access to."""
    calendars = fetch_calendar_list(request.user)
    if not calendars:
        return api.create_response(
            request,
            {"detail": "No Google account connected or unable to fetch calendars"},
            status=400
        )
    return calendars


@calendar_router.get("/events", response=list[GoogleEventOut])
def list_calendar_events(request, start: date, end: date):
    """Fetch events from Google Calendar for a date range."""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    events = fetch_events(request.user, start_dt, end_dt)
    return events


@calendar_router.get("/events/cached", response=list[CalendarEventOut])
def list_cached_calendar_events(request, start: date, end: date):
    """Fetch cached calendar events from the database."""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    return get_cached_events(request.user, start_dt, end_dt)


@calendar_router.get("/sync-states", response=list[CalendarSyncStateOut])
def list_sync_states(request):
    """List all calendar sync states for the user."""
    states = CalendarSyncState.objects.filter(user=request.user)
    return [
        {
            "id": s.id,
            "calendar_id": s.calendar_id,
            "calendar_name": s.calendar_name,
            "calendar_color": s.calendar_color,
            "is_enabled": s.is_enabled,
            "last_synced_at": s.last_synced_at,
            "has_sync_token": bool(s.sync_token),
        }
        for s in states
    ]


@calendar_router.post("/sync", response=list[SyncResultOut])
def trigger_sync(request):
    """
    Trigger sync for all enabled calendars.
    Uses incremental sync when possible, falls back to full sync.
    """
    results = sync_all_calendars(request.user)
    return [
        {
            "calendar_id": r.calendar_id,
            "created": r.created,
            "updated": r.updated,
            "deleted": r.deleted,
            "errors": r.errors,
            "full_sync_performed": r.full_sync_performed,
        }
        for r in results
    ]


@llm_router.post("/generate-schedule", response=ProposedPlanOut)
def generate_schedule(request):
    """Generate a daily schedule using LLM."""
    plan = generate_daily_plan(request.user)
    return {
        "message": plan.message,
        "schedule": [
            {
                "task_id": slot.task_id,
                "start_time": slot.start_time,
                "estimated_minutes": slot.estimated_minutes,
            }
            for slot in plan.schedule
        ],
    }


@llm_router.post("/commit-schedule", response=OkResponse)
def commit_schedule(request, data: CommitScheduleIn):
    """Commit the proposed schedule by updating task scheduled times."""
    today = date.today()

    for slot in data.slots:
        task = Task.objects.filter(id=slot.task_id, user=request.user).first()
        if task:
            # Parse time strings and combine with today's date
            start_time = datetime.strptime(slot.start_time, "%H:%M").time()
            end_time = datetime.strptime(slot.end_time, "%H:%M").time()

            task.scheduled_start = timezone.make_aware(
                datetime.combine(today, start_time)
            )
            task.scheduled_end = timezone.make_aware(
                datetime.combine(today, end_time)
            )
            task.save()

    return {"ok": True}


api.add_router("/auth", auth_router)
api.add_router("/projects", projects_router)
api.add_router("/tasks", tasks_router)
api.add_router("/subtasks", subtasks_router)
api.add_router("/settings", settings_router)
api.add_router("/calendar", calendar_router)
api.add_router("/llm", llm_router)
