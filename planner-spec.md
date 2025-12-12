# Planner - Product Specification

> A personal planning tool for people juggling multiple projects (PhD + startup, multiple roles, etc.)

## 1. Overview

### Vision

A kanban-style task manager with LLM-powered task parsing and scheduling. Unlike existing tools (Todoist, TickTick, Notion), Planner combines:

- **Board + Calendar** in one view (toggleable)
- **Flexible grouping** - view tasks by time horizon OR by project
- **LLM intelligence** - natural language task entry, auto-scheduling, smart estimates
- **Simplicity** - not trying to be Notion, just tasks and projects

### Target User

- PhD students, startup founders, or anyone with multiple concurrent projects
- Needs to see everything in one place
- Wants keyboard-first, fast interaction
- Comfortable with AI assistance

### Core Philosophy

1. **Simple data model** - Projects contain tasks, that's it
2. **Flexible views** - Same data, different lenses (time vs project)
3. **LLM as invisible helper** - Parses input, schedules tasks, no chatbot UI
4. **Keyboard-first** - Cmd+K for everything

---

## 2. Extension Levels

Build incrementally. Each level is usable standalone.

### Level 0: Core (v1 target)

- Google OAuth login
- Projects (CRUD)
- Tasks (CRUD, drag/drop reorder)
- Kanban board with columns
- Toggle grouping: by time | by project
- Quick add modal (Cmd+K) with LLM parsing
- Mark tasks complete

### Level 1: Calendar Read (future)

- Everything in Level 0
- Hideable calendar sidebar
- Read-only Google Calendar events
- Day/week view toggle

### Level 2: Manual Scheduling (future)

- Everything in Level 1
- Drag task → calendar to schedule
- Tasks appear as blocks on calendar
- Drag on calendar to reschedule

### Level 3: Auto-scheduling (future)

- Everything in Level 2
- User preferences text field (for LLM context)
- LLM auto-schedules tasks with due date + estimate
- LLM estimates duration if not provided

### Level 4: Morning Email & Reschedule (future)

- Everything in Level 3
- Daily morning email with schedule
- End of day: LLM reschedules incomplete tasks
- Email warnings (overdue, packed schedule, pushed to weekend)

### Level 5: Calendar Write (future)

- Everything in Level 4
- Push scheduled tasks to Google Calendar
- Two-way sync

---

## 3. Tech Stack

### Backend

- **Framework**: Django 5.x
- **API**: Django Ninja (fast, typed, OpenAPI)
- **Database**: PostgreSQL (SaaS - Neon, Supabase, or similar)
- **Auth**: Google OAuth via `django-allauth`
- **LLM**: Anthropic Claude API (`anthropic` Python SDK)

### Frontend

- **Framework**: SvelteKit
- **Styling**: Tailwind CSS
- **Drag/Drop**: `svelte-dnd-action`
- **Calendar** (future): FullCalendar
- **HTTP Client**: Native fetch or `ky`

### Infrastructure

- Docker / Docker Compose for local dev
- Dockerfile for deployment
- SaaS PostgreSQL (no self-managed DB)

### Key Dependencies

**Backend (requirements.txt)**:
```
django>=5.0
django-ninja>=1.0
django-allauth>=0.60
anthropic>=0.40
psycopg2-binary
python-dotenv
gunicorn
django-cors-headers
```

**Frontend (package.json)**:
```json
{
  "dependencies": {
    "svelte-dnd-action": "^0.9",
    "tailwindcss": "^3.4"
  },
  "devDependencies": {
    "@sveltejs/kit": "^2.0",
    "svelte": "^4.0"
  }
}
```

---

## 4. Data Model

### User

Extends Django's AbstractUser or uses default User with related UserSettings.

### UserSettings

```python
class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Scheduling preferences (free text for LLM) - Level 3+
    scheduling_preferences = models.TextField(blank=True)

    # Email settings - Level 4+
    morning_email_time = models.TimeField(default="06:00")
    morning_email_enabled = models.BooleanField(default=True)

    # Google Calendar - Level 1+
    google_refresh_token = models.TextField(blank=True)
    synced_calendar_ids = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Project

```python
class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    color = models.CharField(max_length=7)  # hex color, e.g., "#3B82F6"
    archived = models.BooleanField(default=False)
    position = models.IntegerField(default=0)  # for ordering
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'created_at']
```

### Task

```python
class Task(models.Model):
    class TimeHorizon(models.TextChoices):
        TODAY = 'today', 'Today'
        THIS_WEEK = 'this_week', 'This Week'
        NEXT_WEEK = 'next_week', 'Next Week'
        LATER = 'later', 'Later'
        BACKLOG = 'backlog', 'Backlog'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)

    # Core fields
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    # Kanban position
    time_horizon = models.CharField(
        max_length=20,
        choices=TimeHorizon.choices,
        default=TimeHorizon.BACKLOG
    )
    position = models.IntegerField(default=0)  # ordering within column

    # Planning
    due_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.IntegerField(null=True, blank=True)

    # Scheduling - Level 2+
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    # Google Calendar sync - Level 5+
    gcal_event_id = models.CharField(max_length=200, blank=True)

    # Status
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'created_at']
```

### CalendarEvent (Level 1+)

```python
class CalendarEvent(models.Model):
    """Read-only events from Google Calendar"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    gcal_id = models.CharField(max_length=200)
    calendar_id = models.CharField(max_length=200)
    title = models.CharField(max_length=500)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'gcal_id']
```

---

## 5. API Specification

Base URL: `/api/`

All endpoints require authentication (except auth endpoints).

### Auth

```
POST /api/auth/google
  Body: { "code": "oauth_code_from_frontend" }
  Response: { "token": "session_token", "user": { ... } }

POST /api/auth/logout
  Response: { "ok": true }

GET /api/auth/me
  Response: { "user": { "id", "email", "name" } }
```

### Projects

```
GET /api/projects
  Response: [{ "id", "name", "color", "position", "archived" }, ...]

POST /api/projects
  Body: { "name": "LLM Paper", "color": "#3B82F6" }
  Response: { "id", "name", "color", ... }

PATCH /api/projects/{id}
  Body: { "name"?: string, "color"?: string, "archived"?: boolean }
  Response: { "id", "name", "color", ... }

DELETE /api/projects/{id}
  Response: { "ok": true }

PATCH /api/projects/reorder
  Body: { "order": [3, 1, 2] }  // project IDs in new order
  Response: { "ok": true }
```

### Tasks

```
GET /api/tasks
  Query params:
    - project_id?: number (filter by project)
    - time_horizon?: string (filter by column)
    - completed?: boolean
  Response: [{ "id", "title", "project", "time_horizon", "due_date", ... }, ...]

POST /api/tasks
  Body: {
    "title": "Write intro",
    "project_id"?: number,
    "time_horizon"?: string (default: "backlog"),
    "due_date"?: "YYYY-MM-DD",
    "estimated_minutes"?: number,
    "description"?: string
  }
  Response: { "id", "title", ... }

PATCH /api/tasks/{id}
  Body: { any task fields to update }
  Response: { "id", "title", ... }

DELETE /api/tasks/{id}
  Response: { "ok": true }

PATCH /api/tasks/{id}/move
  Body: {
    "time_horizon": "today",
    "position": 2,
    "project_id"?: number  // for "by project" view moves
  }
  Response: { "ok": true }

POST /api/tasks/{id}/complete
  Response: { "id", "completed": true, "completed_at": "..." }

POST /api/tasks/{id}/uncomplete
  Response: { "id", "completed": false, "completed_at": null }
```

### LLM

```
POST /api/llm/parse-task
  Body: { "text": "review patrick's draft by friday for llm paper ~1hr" }
  Response: {
    "title": "Review Patrick's draft",
    "project_name": "LLM Paper",  // matched or null
    "project_id": 3,              // matched or null
    "due_date": "2024-12-13",
    "estimated_minutes": 60
  }
```

### Calendar (Level 1+)

```
GET /api/calendar/events
  Query params:
    - start: "YYYY-MM-DD"
    - end: "YYYY-MM-DD"
  Response: [{ "id", "title", "start", "end", "all_day" }, ...]

POST /api/calendar/sync
  Triggers a sync with Google Calendar
  Response: { "synced": 42 }
```

### Scheduling (Level 3+)

```
POST /api/tasks/{id}/auto-schedule
  LLM finds best slot and schedules the task
  Response: {
    "scheduled_start": "...",
    "scheduled_end": "...",
    "reasoning": "Scheduled for Thursday morning - you have a 2hr free block"
  }
```

### Settings

```
GET /api/settings
  Response: { "scheduling_preferences", "morning_email_time", "morning_email_enabled" }

PATCH /api/settings
  Body: { any settings fields }
  Response: { ... }
```

---

## 6. UI/UX Specification

### Layout: Main Dashboard

Primary screen - board + calendar side by side, both hideable.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Planner                      [Cmd+K]    [Board ☑] [Calendar ☑]   [Avatar] │
├────────────────────────────────────────────────────────────────────────────┤
│  Group: [Time ▼] [Project]                    Filter: [All projects ▼]    │
├───────────────────────────────────┬────────────────────────────────────────┤
│                                   │                                        │
│          BOARD                    │           CALENDAR                     │
│                                   │                                        │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ │     ◀ Wed, December 11 ▶              │
│  │Today│ │Week │ │Later│ │Back │ │                                        │
│  │     │ │     │ │     │ │log  │ │  09:00 ░░░░░░░░░░░░░░░░░░░            │
│  │┌───┐│ │┌───┐│ │┌───┐│ │┌───┐│ │        Daily Catch-up                 │
│  ││   ││ ││   ││ ││   ││ ││   ││ │  10:00 ░░░░░░░░░░░░░░░░░░░            │
│  │└───┘│ │└───┘│ │└───┘│ │└───┘│ │        Econometrics                   │
│  │┌───┐│ │┌───┐│ │     │ │┌───┐│ │  11:00                                │
│  ││   ││ ││   ││ │     │ ││   ││ │  12:00 ░░░░░░░░░░░░░░░░░░░            │
│  │└───┘│ │└───┘│ │     │ │└───┘│ │        Brownbag                       │
│  │     │ │     │ │     │ │     │ │  13:00                                │
│  └─────┘ └─────┘ └─────┘ └─────┘ │  14:00 ┌─────────────────────┐        │
│                                   │        │ Task block          │        │
│                                   │  15:00 └─────────────────────┘        │
│                                   │                                        │
└───────────────────────────────────┴────────────────────────────────────────┘
```

### Layout: Board Only

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Planner                      [Cmd+K]    [Board ☑] [Calendar ☐]   [Avatar] │
├────────────────────────────────────────────────────────────────────────────┤
│  Group: [Time ▼] [Project]                    Filter: [All projects ▼]    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│   │   Today    │  │ This Week  │  │   Later    │  │  Backlog   │          │
│   │            │  │            │  │            │  │            │          │
│   │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │          │
│   │ │🔵 Write│ │  │ │🟢 Fix  │ │  │ │🟡 Pset │ │  │ │🟢 Refac│ │          │
│   │ │  intro │ │  │ │  auth  │ │  │ │  4     │ │  │ │  tor   │ │          │
│   │ │Fri·2hr │ │  │ │  bug   │ │  │ │Mon     │ │  │ │  API   │ │          │
│   │ └────────┘ │  │ │~1hr    │ │  │ └────────┘ │  │ └────────┘ │          │
│   │ ┌────────┐ │  │ └────────┘ │  │            │  │ ┌────────┐ │          │
│   │ │🟢 Revie│ │  │ ┌────────┐ │  │            │  │ │🔵 Write│ │          │
│   │ │  w PR  │ │  │ │🔵 Run  │ │  │            │  │ │  resul │ │          │
│   │ │~30min  │ │  │ │  expts │ │  │            │  │ │  ts    │ │          │
│   │ └────────┘ │  │ │~3hr    │ │  │            │  │ └────────┘ │          │
│   │            │  │ └────────┘ │  │            │  │            │          │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘          │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Layout: Grouped by Project

When "Group: Project" is selected, columns become projects:

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Planner                      [Cmd+K]    [Board ☑] [Calendar ☐]   [Avatar] │
├────────────────────────────────────────────────────────────────────────────┤
│  Group: [Time] [Project ▼]                    Filter: [This Week ▼]       │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│   │ 🔵 LLM     │  │ 🟢 Startup │  │ 🟡 Econ    │  │ 🟣 DDMind  │          │
│   │    Paper   │  │            │  │            │  │            │          │
│   │            │  │            │  │            │  │            │          │
│   │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │          │
│   │ │ Write  │ │  │ │ Review │ │  │ │ Pset 4 │ │  │ │ User   │ │          │
│   │ │ intro  │ │  │ │ PR #42 │ │  │ │        │ │  │ │ study  │ │          │
│   │ │⚑ Fri   │ │  │ │⚑ Today │ │  │ │⚑ Mon   │ │  │ │⚑ Next  │ │          │
│   │ └────────┘ │  │ └────────┘ │  │ └────────┘ │  │ │  wk    │ │          │
│   │ ┌────────┐ │  │ ┌────────┐ │  │            │  │ └────────┘ │          │
│   │ │ Run    │ │  │ │ Fix    │ │  │            │  │            │          │
│   │ │ expts  │ │  │ │ auth   │ │  │            │  │            │          │
│   │ │⚑ Thu   │ │  │ │ bug    │ │  │            │  │            │          │
│   │ └────────┘ │  │ └────────┘ │  │            │  │            │          │
│   │            │  │            │  │            │  │            │          │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘          │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Task Card

```
┌─────────────────────┐
│ Write intro section │  ← title
│ 🔵 LLM Paper        │  ← project color + name
│ ⚑ Fri · ~2hr        │  ← due date + estimate (if present)
└─────────────────────┘
```

Completed task (faded, strikethrough):
```
┌─────────────────────┐
│ ✓ Review PR #42     │  ← strikethrough, muted colors
│ 🟢 Startup          │
└─────────────────────┘
```

### Quick Add Modal (Cmd+K)

Triggered by Cmd+K (Mac) or Ctrl+K (Windows/Linux).

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ review patrick's draft by friday for llm paper ~1hr     │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   Parsing...                                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

After LLM parses:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ review patrick's draft by friday for llm paper ~1hr     │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Title:    Review Patrick's draft                       │   │
│   │  Project:  🔵 LLM Paper                    [change ▼]   │   │
│   │  Due:      Friday, Dec 13                  [change]     │   │
│   │  Estimate: 1 hour                          [change]     │   │
│   │  Column:   This Week                       [change ▼]   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                              [Cancel]  [Create Task ⏎]          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

User can edit any field before confirming. Enter key creates task.

### Settings Page

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Settings                                                         [← Back] │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ACCOUNT                                                                   │
│  ─────────────────────────────────────────────────────────────────────     │
│  Email            david@example.com                                        │
│  Google Calendar  ✓ Connected                            [Manage]          │
│                                                                            │
│  PROJECTS                                                                  │
│  ─────────────────────────────────────────────────────────────────────     │
│  🔵 LLM Paper                                    [Edit] [Archive]          │
│  🟢 Startup                                      [Edit] [Archive]          │
│  🟡 Econ Course                                  [Edit] [Archive]          │
│  🟣 DDMind                                       [Edit] [Archive]          │
│                                              [+ New Project]               │
│                                                                            │
│  SCHEDULING PREFERENCES (Level 3+)                                         │
│  ─────────────────────────────────────────────────────────────────────     │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ I prefer deep work in mornings. Don't schedule before 8:30am.       │ │
│  │ Friday evenings off. Weekends only for urgent stuff.                │ │
│  │ Max schedule 1 week out.                                             │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  MORNING EMAIL (Level 4+)                                                  │
│  ─────────────────────────────────────────────────────────────────────     │
│  Send daily summary at  [6:00 AM ▼]                                        │
│  ☑ Include rescheduled tasks                                               │
│  ☑ Include warnings                                                        │
│                                                                            │
│                                                          [Save Settings]   │
└────────────────────────────────────────────────────────────────────────────┘
```

### Empty States

**No projects yet:**
```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│                    Welcome to Planner!                                     │
│                                                                            │
│                    Create your first project                               │
│                    to get started.                                         │
│                                                                            │
│                    [+ Create Project]                                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**No tasks in column:**
```
┌────────────┐
│   Today    │
│            │
│  No tasks  │
│            │
│  [+ Add]   │
│            │
└────────────┘
```

### Component List

**Layout:**
- `Header` - top nav with logo, Cmd+K button, avatar
- `Dashboard` - main container, manages board/calendar visibility
- `Board` - kanban board container
- `Calendar` - calendar sidebar (Level 1+)

**Board:**
- `Column` - single kanban column (Today, This Week, etc.)
- `TaskCard` - individual task card
- `ColumnHeader` - column title + task count

**Modals:**
- `QuickAddModal` - Cmd+K task entry
- `TaskEditModal` - full task editor (click on task)
- `ProjectModal` - create/edit project
- `SettingsModal` or page

**Common:**
- `Button`
- `Input`
- `Select` / `Dropdown`
- `ColorPicker` (for projects)
- `DatePicker`
- `Avatar`
- `Toggle`

---

## 7. User Flows

### Sign Up / Login

```
1. User visits app
2. Sees login page with "Sign in with Google" button
3. Clicks button → redirected to Google OAuth
4. Google shows permissions: email + calendar access
5. User approves → redirected back
6. Backend creates User + UserSettings
7. Frontend stores session, redirects to dashboard
8. First-time: show empty state with "Create your first project"
```

### Create Project

```
1. User clicks [+ New Project] or sees empty state prompt
2. Modal opens with:
   - Name input
   - Color picker (preset colors)
3. User fills in, clicks Create
4. Project appears in settings list
5. Project now available in quick add and filters
```

### Create Task (Quick Add)

```
1. User presses Cmd+K
2. Modal opens with input focused
3. User types: "review patrick's draft by friday for llm paper ~1hr"
4. User presses Enter or waits 500ms
5. Frontend calls POST /api/llm/parse-task
6. LLM returns parsed fields
7. Modal shows parsed result with editable fields
8. User reviews, optionally edits
9. User presses Enter or clicks "Create Task"
10. Frontend calls POST /api/tasks
11. Modal closes
12. Task appears in appropriate column
```

### Drag Task Between Columns

```
1. User grabs task card in "Backlog"
2. Drags to "This Week" column
3. Drops at desired position
4. Frontend calls PATCH /api/tasks/{id}/move
5. Backend updates time_horizon and position
6. UI reflects new position
```

### Complete Task

```
1. User clicks checkbox on task card (or dedicated complete button)
2. Frontend calls POST /api/tasks/{id}/complete
3. Task visually marked complete (strikethrough, faded)
4. Task moves to bottom of column or separate "Done" section
```

### Toggle Board Grouping

```
1. User clicks "Project" in "Group: [Time] [Project]" toggle
2. Board re-renders with project columns instead of time columns
3. Filter changes to time-based options (Today, This Week, etc.)
4. Tasks reorganized by project
```

---

## 8. LLM Integration

### Task Parsing

**Endpoint:** `POST /api/llm/parse-task`

**Input:**
```json
{
  "text": "review patrick's draft by friday for llm paper ~1hr"
}
```

**Prompt:**
```
Parse this task input into structured data.

User input: "{text}"

Available projects (match if mentioned):
{list of user's projects with IDs}

Today's date: {date}

Extract:
- title: Clean task title (imperative form)
- project_name: Matched project name or null
- project_id: Matched project ID or null
- due_date: ISO date string or null
- estimated_minutes: Number or null

Respond with JSON only, no explanation.
```

**Output:**
```json
{
  "title": "Review Patrick's draft",
  "project_name": "LLM Paper",
  "project_id": 3,
  "due_date": "2024-12-13",
  "estimated_minutes": 60
}
```

**Model:** Claude claude-sonnet-4-20250514 (fast, cheap, good enough for parsing)

### Time Estimation (Level 3+)

If user doesn't provide estimate, LLM guesses based on task type:

```
Estimate time for this task in minutes.

Task: "{title}"
Project: "{project_name}"

Guidelines:
- Quick admin tasks (emails, reviews): 15-30 min
- Medium tasks (small coding, short writing): 30-60 min
- Deep work (writing sections, complex coding): 90-180 min
- Large tasks (full features, paper drafts): 180-300 min

Respond with just a number (minutes).
```

### Auto-scheduling (Level 3+)

**Prompt:**
```
Schedule this task onto the user's calendar.

TASK:
- Title: {title}
- Project: {project}
- Due: {due_date}
- Estimate: {estimated_minutes} minutes

USER PREFERENCES:
{user's scheduling_preferences text}

CALENDAR (next 7 days):
{formatted calendar events}

ALREADY SCHEDULED TASKS:
{formatted scheduled tasks}

RULES:
- Find the best time slot before the due date
- Leave 15min buffer around meetings
- Respect user preferences
- Don't schedule more than 1 week out
- Prefer morning for deep work tasks

Return JSON:
{
  "scheduled_start": "ISO datetime",
  "scheduled_end": "ISO datetime",
  "reasoning": "brief explanation"
}
```

---

## 9. Project Structure

### Backend

```
backend/
├── planner/
│   ├── __init__.py
│   ├── settings.py          # Django settings
│   ├── urls.py               # URL routing
│   └── wsgi.py
├── core/
│   ├── __init__.py
│   ├── models.py             # User, Project, Task, etc.
│   ├── api.py                # Django Ninja API endpoints
│   ├── schemas.py            # Pydantic schemas for API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py            # Anthropic integration
│   │   ├── calendar.py       # Google Calendar (Level 1+)
│   │   └── scheduler.py      # Auto-scheduling (Level 3+)
│   ├── migrations/
│   └── admin.py
├── manage.py
├── requirements.txt
├── Dockerfile
└── .env.example
```

### Frontend

```
frontend/
├── src/
│   ├── routes/
│   │   ├── +page.svelte          # Dashboard (main page)
│   │   ├── +layout.svelte        # App layout
│   │   ├── login/
│   │   │   └── +page.svelte      # Login page
│   │   └── settings/
│   │       └── +page.svelte      # Settings page
│   ├── lib/
│   │   ├── components/
│   │   │   ├── Header.svelte
│   │   │   ├── Board.svelte
│   │   │   ├── Column.svelte
│   │   │   ├── TaskCard.svelte
│   │   │   ├── QuickAddModal.svelte
│   │   │   ├── TaskEditModal.svelte
│   │   │   ├── ProjectModal.svelte
│   │   │   └── Calendar.svelte    # Level 1+
│   │   ├── stores/
│   │   │   ├── auth.ts
│   │   │   ├── projects.ts
│   │   │   └── tasks.ts
│   │   ├── api.ts                 # API client
│   │   └── types.ts               # TypeScript types
│   └── app.html
├── static/
├── package.json
├── svelte.config.js
├── tailwind.config.js
├── tsconfig.json
├── Dockerfile
└── .env.example
```

### Root

```
planner/
├── backend/
├── frontend/
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

## 10. Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Google Cloud project with OAuth credentials
- Anthropic API key

### Environment Variables

**Backend (.env):**
```
DEBUG=true
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost:5432/planner

# Google OAuth
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:5173
```

**Frontend (.env):**
```
PUBLIC_API_URL=http://localhost:8000/api
PUBLIC_GOOGLE_CLIENT_ID=xxx
```

### Local Development

**Option A: Docker Compose (recommended)**
```bash
docker-compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

**Option B: Manual**
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Database Setup

For local dev, use Docker Compose which includes Postgres.

For production, use a SaaS PostgreSQL:
- Neon (recommended, generous free tier)
- Supabase
- Railway
- Render

Set `DATABASE_URL` to the connection string.

### Google OAuth Setup

1. Go to Google Cloud Console
2. Create project (or use existing)
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URIs:
   - `http://localhost:5173/auth/callback` (dev)
   - `https://yourapp.com/auth/callback` (prod)
6. Copy Client ID and Client Secret to .env

---

## 11. Future Considerations

### Calendar Integration (Level 1-2)

**Reading events:**
- Sync on login and periodically (every 15 min?)
- Store in CalendarEvent model
- Only sync next 14 days to limit data

**Manual scheduling (Level 2):**
- Tasks get `scheduled_start` and `scheduled_end`
- Frontend renders on calendar alongside Google events
- Drag interactions update these fields

### Auto-scheduling (Level 3)

**Trigger:** When task is created with due_date (and optionally estimate)

**Process:**
1. Fetch user's calendar events for next 7 days
2. Fetch already-scheduled tasks
3. Send to LLM with user preferences
4. LLM returns suggested slot
5. Update task with scheduled times

**Edge cases:**
- No available slot → schedule anyway, flag in response
- Conflicts → LLM should avoid, but handle gracefully

### Morning Email (Level 4)

**Implementation:**
- Django management command run via cron
- For each user with morning_email_enabled:
  - Get today's schedule (calendar + tasks)
  - Get rescheduled tasks from yesterday
  - Generate email content (could use LLM for summary)
  - Send via SendGrid/Postmark/SES

**Reschedule logic (run end of day):**
- Find tasks scheduled for today that aren't completed
- For each, run auto-schedule to find new slot
- Record that it was rescheduled (for morning email)

### Mobile

- SvelteKit renders responsively
- Board columns stack vertically on mobile
- Consider bottom nav instead of header
- Swipe gestures for column navigation (future)

### Offline Support (far future)

- Service worker for offline access
- Queue mutations, sync when online
- Complex, defer unless needed

---

## 12. Acceptance Criteria (Level 0)

The MVP is complete when:

- [ ] User can sign in with Google
- [ ] User can create/edit/delete projects
- [ ] User can create tasks via quick add (Cmd+K)
- [ ] LLM parses natural language into task fields
- [ ] User can edit parsed fields before creating
- [ ] Tasks appear on kanban board
- [ ] User can drag tasks between columns
- [ ] User can toggle board grouping (time/project)
- [ ] User can filter by project
- [ ] User can mark tasks complete
- [ ] User can edit existing tasks
- [ ] User can delete tasks
- [ ] Board/calendar panels can be hidden (calendar empty for Level 0)
- [ ] Responsive layout works on tablet/desktop
- [ ] App runs in Docker
- [ ] Deployable with SaaS database

---

## Appendix: Color Palette

Default project colors:
```
Blue:    #3B82F6
Green:   #22C55E
Yellow:  #EAB308
Purple:  #A855F7
Pink:    #EC4899
Orange:  #F97316
Teal:    #14B8A6
Red:     #EF4444
```

UI colors (Tailwind):
```
Background: gray-50
Card:       white
Border:     gray-200
Text:       gray-900
Muted:      gray-500
```
