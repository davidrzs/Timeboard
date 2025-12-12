# Timeboard

A kanban-style task manager with LLM-powered task parsing. Features a board + calendar view, flexible grouping by time horizon or project, and natural language task entry.

## Tech Stack

- **Backend**: Django 6 + Django Ninja, PostgreSQL
- **Frontend**: SvelteKit (Svelte 5), Tailwind CSS 4, TypeScript
- **Auth**: Google OAuth via django-allauth
- **LLM**: OpenAI for natural language task parsing

## Quick Start (Development)

**Backend** (requires Python 3.12+, [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
cp .env.example .env  # Configure environment variables
uv run python manage.py migrate
uv run python manage.py runserver
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev
```

## Deployment (Dokploy)

1. Create a new Compose project in Dokploy pointing to this repository
2. Configure environment variables (see `.env.example`):
   - `DATABASE_URL` - External PostgreSQL connection string
   - `SECRET_KEY` - Django secret key
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - OAuth credentials
   - `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, `ALLOWED_HOSTS` - Your domain
   - `PUBLIC_API_URL` - Backend API URL (e.g., `https://api.example.com/api`)
   - `OPENAI_API_KEY` - For LLM task parsing (optional)
3. Set up domains/routing:
   - Backend serves on port 8000
   - Frontend serves on port 3000
4. Deploy

## Environment Variables

See `.env.example` for all available options.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Django secret key |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `FRONTEND_URL` | Frontend URL for redirects |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins |
| `ALLOWED_HOSTS` | Django allowed hosts |
| `PUBLIC_API_URL` | API URL used by frontend |
| `OPENAI_API_KEY` | OpenAI API key (optional) |

## Development Commands

```bash
# Backend
uv run python manage.py runserver      # Dev server
uv run python manage.py makemigrations # Create migrations
uv run python manage.py migrate        # Apply migrations

# Frontend
npm run dev     # Dev server
npm run build   # Production build
npm run check   # Type checking
```
