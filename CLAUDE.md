# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timeboard is a kanban-style task manager with Google Calendar integration. Features a board view with flexible grouping by time horizon or project. Tasks are organized into columns (Today, This Week, Next Week, Later, Backlog) based on their due date.

## Tech Stack

- **Backend**: Django 6.x with Django Ninja (typed REST API), PostgreSQL
- **Frontend**: SvelteKit (Svelte 5), Tailwind CSS 4, TypeScript
- **Auth**: Google OAuth via django-allauth
- **Calendar**: Google Calendar API with incremental sync

## Development Commands

### Backend (from `backend/`)
```bash
uv run python manage.py runserver      # Dev server on :8000
uv run python manage.py migrate        # Apply migrations
uv run python manage.py makemigrations # Create migrations
```

### Frontend (from `frontend/`)
```bash
npm run dev       # Dev server on :5173
npm run build     # Production build
npm run check     # TypeScript/Svelte type checking
```

### Docker (from root)
```bash
docker-compose up  # Starts db, backend (:8000), frontend (:5173)
```

## Architecture

### Backend Structure (`backend/`)
- `planner/` - Django project settings and URL configuration
- `core/` - Main app with all business logic:
  - `models.py` - Data models: UserSettings, Project, Task, Subtask, CalendarEvent, CalendarSyncState
  - `api.py` - Django Ninja API endpoints with session auth
  - `schemas.py` - Pydantic request/response schemas
  - `services/calendar.py` - Google Calendar sync with incremental updates

API routers: `/api/auth/`, `/api/projects/`, `/api/tasks/`, `/api/subtasks/`, `/api/settings/`, `/api/calendar/`

### Frontend Structure (`frontend/src/`)
- `routes/` - SvelteKit pages (+page.svelte, +layout.svelte)
- `lib/components/` - UI components: Board, Column, TaskCard, QuickAddModal, TaskEditModal, ProjectModal, Calendar, Header
- `lib/stores/` - Svelte stores: auth.ts, projects.ts, tasks.ts, settings.ts, ui.ts
- `lib/api.ts` - Typed API client wrapping all backend endpoints
- `lib/types.ts` - TypeScript interfaces matching backend schemas

### Key Architectural Patterns

**Time Horizon as Computed Property**: Tasks don't store `time_horizon` directly. It's computed from `due_date` in the model's `time_horizon` property:
- `due_date <= today` → TODAY
- `due_date <= this Sunday` → THIS_WEEK
- `due_date <= next Sunday` → NEXT_WEEK
- `due_date > next Sunday` → LATER
- `due_date is null` → BACKLOG

Moving a task between columns updates its `due_date` via `Task.due_date_for_horizon()`.

**Session Auth**: API uses Django session auth. Frontend uses `credentials: 'include'` on all requests.

**Dev Login**: In DEBUG mode, `/accounts/dev-login/?email=<email>` creates/logs in a user without OAuth.

**Derived Stores**: Frontend has `tasksByHorizon` and `tasksByProject` derived stores that group/sort tasks for rendering.

**Drag & Drop**: Uses `svelte-dnd-action` library.

**Reschedule Tracking**: Tasks track `reschedule_count` - incremented when moved to a later time horizon.

## Environment Variables

Backend (`.env`):
- `DATABASE_URL` - PostgreSQL connection string
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - OAuth credentials
- `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` - CORS config

Frontend uses `PUBLIC_API_URL` (defaults to `http://localhost:8000/api`).
