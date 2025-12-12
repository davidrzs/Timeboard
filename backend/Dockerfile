FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN uv run python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD uv run python manage.py migrate && \
    uv run gunicorn planner.wsgi:application --bind [::]:8000 --workers 2
