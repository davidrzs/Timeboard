from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from allauth.socialaccount.models import SocialAccount, SocialToken
from django.db import transaction
from django.utils import timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..models import CalendarEvent, CalendarSyncState


def get_google_credentials(user) -> Credentials | None:
    """Get Google OAuth credentials for a user."""
    try:
        social_account = SocialAccount.objects.get(user=user, provider="google")
        token = SocialToken.objects.get(account=social_account)

        return Credentials(
            token=token.token,
            refresh_token=token.token_secret,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=token.app.client_id,
            client_secret=token.app.secret,
        )
    except (SocialAccount.DoesNotExist, SocialToken.DoesNotExist):
        return None


def get_calendar_service(user):
    """Get an authenticated Google Calendar service."""
    credentials = get_google_credentials(user)
    if not credentials:
        return None

    return build("calendar", "v3", credentials=credentials)


def fetch_calendar_list(user) -> list[dict[str, Any]]:
    """Fetch all calendars the user has access to."""
    service = get_calendar_service(user)
    if not service:
        return []

    try:
        calendars = []
        page_token = None

        while True:
            calendar_list = service.calendarList().list(pageToken=page_token).execute()

            for calendar in calendar_list.get("items", []):
                calendars.append({
                    "id": calendar["id"],
                    "name": calendar.get("summary", "Untitled"),
                    "color": calendar.get("backgroundColor", "#4285f4"),
                    "primary": calendar.get("primary", False),
                })

            page_token = calendar_list.get("nextPageToken")
            if not page_token:
                break

        return calendars
    except HttpError as e:
        print(f"Error fetching calendar list: {e}")
        return []


@dataclass
class SyncResult:
    """Result of a sync operation."""
    calendar_id: str = ""
    created: int = 0
    updated: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)
    full_sync_performed: bool = False


def _parse_event(event_data: dict, calendar_id: str) -> dict | None:
    """Parse Google Calendar event data into model fields."""
    start = event_data.get("start", {})
    end = event_data.get("end", {})

    if "date" in start:
        # All-day event - parse date and make timezone-aware at midnight UTC
        start_dt = datetime.fromisoformat(start["date"]).replace(tzinfo=dt_timezone.utc)
        end_dt = datetime.fromisoformat(end["date"]).replace(tzinfo=dt_timezone.utc)
        all_day = True
    elif "dateTime" in start:
        # Timed event
        start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
        all_day = False
    else:
        return None

    return {
        "calendar_id": calendar_id,
        "title": event_data.get("summary", "(No title)"),
        "start": start_dt,
        "end": end_dt,
        "all_day": all_day,
        "location": event_data.get("location", ""),
        "description": event_data.get("description", ""),
        "status": event_data.get("status", "confirmed"),
        "etag": event_data.get("etag", ""),
    }


def _do_full_sync(service, user, calendar_id: str, sync_state: CalendarSyncState) -> SyncResult:
    """
    Perform full sync - fetches all events and replaces cached data.
    Used for initial sync or when syncToken expires.
    """
    result = SyncResult(calendar_id=calendar_id, full_sync_performed=True)

    # Fetch events within a reasonable window (30 days back, 1 year forward)
    now = timezone.now()
    time_min = (now - timedelta(days=30)).isoformat()
    time_max = (now + timedelta(days=365)).isoformat()

    all_events = []
    page_token = None
    new_sync_token = ""

    try:
        while True:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                maxResults=250,
                pageToken=page_token,
            ).execute()

            all_events.extend(events_result.get("items", []))
            page_token = events_result.get("nextPageToken")

            if not page_token:
                new_sync_token = events_result.get("nextSyncToken", "")
                break
    except HttpError as e:
        result.errors.append(f"API error during full sync: {e}")
        return result

    with transaction.atomic():
        # Delete all existing events for this calendar
        deleted_count, _ = CalendarEvent.objects.filter(
            user=user,
            calendar_id=calendar_id
        ).delete()
        result.deleted = deleted_count

        # Create new events
        for event_data in all_events:
            if event_data.get("status") == "cancelled":
                continue
            parsed = _parse_event(event_data, calendar_id)
            if parsed:
                CalendarEvent.objects.create(
                    user=user,
                    gcal_id=event_data["id"],
                    **parsed
                )
                result.created += 1

        # Update sync state
        sync_state.sync_token = new_sync_token
        sync_state.last_synced_at = timezone.now()
        sync_state.save()

    return result


def _do_incremental_sync(service, user, calendar_id: str, sync_state: CalendarSyncState) -> SyncResult:
    """
    Perform incremental sync using syncToken.
    Only fetches changed events since last sync.
    """
    result = SyncResult(calendar_id=calendar_id)

    all_changes = []
    page_token = None
    new_sync_token = ""

    try:
        while True:
            request_params = {
                "calendarId": calendar_id,
                "syncToken": sync_state.sync_token,
                "maxResults": 250,
            }
            if page_token:
                request_params["pageToken"] = page_token

            events_result = service.events().list(**request_params).execute()
            all_changes.extend(events_result.get("items", []))

            page_token = events_result.get("nextPageToken")
            if not page_token:
                new_sync_token = events_result.get("nextSyncToken", "")
                break
    except HttpError as e:
        if e.resp.status == 410:
            # Token expired - signal that full sync is needed
            raise
        result.errors.append(f"API error during incremental sync: {e}")
        return result

    with transaction.atomic():
        for event_data in all_changes:
            gcal_id = event_data["id"]

            if event_data.get("status") == "cancelled":
                # Event was deleted
                deleted, _ = CalendarEvent.objects.filter(
                    user=user, gcal_id=gcal_id
                ).delete()
                if deleted:
                    result.deleted += 1
            else:
                # Event was created or updated
                parsed = _parse_event(event_data, calendar_id)
                if parsed:
                    obj, created = CalendarEvent.objects.update_or_create(
                        user=user,
                        gcal_id=gcal_id,
                        defaults=parsed
                    )
                    if created:
                        result.created += 1
                    else:
                        result.updated += 1

        # Update sync state
        sync_state.sync_token = new_sync_token
        sync_state.last_synced_at = timezone.now()
        sync_state.save()

    return result


def perform_sync(user, calendar_id: str) -> SyncResult:
    """
    Perform sync for a specific calendar.
    Uses incremental sync when possible, falls back to full sync.
    """
    result = SyncResult(calendar_id=calendar_id)
    service = get_calendar_service(user)
    if not service:
        result.errors.append("No Google credentials available")
        return result

    # Get or create sync state
    sync_state, _ = CalendarSyncState.objects.get_or_create(
        user=user,
        calendar_id=calendar_id,
        defaults={"calendar_name": calendar_id}
    )

    try:
        if sync_state.sync_token:
            # Try incremental sync
            result = _do_incremental_sync(service, user, calendar_id, sync_state)
        else:
            # Full sync (first time)
            result = _do_full_sync(service, user, calendar_id, sync_state)

    except HttpError as e:
        if e.resp.status == 410:
            # Token expired - clear and retry with full sync
            sync_state.sync_token = ""
            sync_state.save()
            result = _do_full_sync(service, user, calendar_id, sync_state)
        else:
            result.errors.append(f"API error: {e}")

    return result


def sync_all_calendars(user) -> list[SyncResult]:
    """
    Sync all calendars for a user.
    Auto-enables sync for all calendars if none are enabled.
    """
    results = []

    # Check if user has any sync states
    sync_states = CalendarSyncState.objects.filter(user=user, is_enabled=True)

    if not sync_states.exists():
        # First time: auto-enable all calendars
        calendars = fetch_calendar_list(user)
        for cal in calendars:
            CalendarSyncState.objects.get_or_create(
                user=user,
                calendar_id=cal["id"],
                defaults={
                    "calendar_name": cal["name"],
                    "calendar_color": cal["color"],
                    "is_enabled": True,
                }
            )
        sync_states = CalendarSyncState.objects.filter(user=user, is_enabled=True)

    # Sync each enabled calendar
    for sync_state in sync_states:
        result = perform_sync(user, sync_state.calendar_id)
        results.append(result)

    return results


def get_cached_events(user, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
    """
    Get cached calendar events from the database.
    Only returns events from enabled calendars.
    """
    enabled_calendar_ids = CalendarSyncState.objects.filter(
        user=user, is_enabled=True
    ).values_list("calendar_id", flat=True)

    return list(CalendarEvent.objects.filter(
        user=user,
        calendar_id__in=enabled_calendar_ids,
        status__in=["confirmed", "tentative"],
        start__lte=end_date,
        end__gte=start_date,
    ).order_by("start"))


# Keep fetch_events for backwards compatibility / live fetching
def fetch_events(user, start_date: datetime, end_date: datetime, calendar_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Fetch events from calendars within a date range (live from Google API).
    If calendar_ids is None, fetches from all calendars.
    """
    service = get_calendar_service(user)
    if not service:
        return []

    # If no specific calendars, get all
    if calendar_ids is None:
        calendars = fetch_calendar_list(user)
        calendar_ids = [c["id"] for c in calendars]

    events = []
    time_min = start_date.isoformat() + "Z"
    time_max = end_date.isoformat() + "Z"

    for calendar_id in calendar_ids:
        try:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            ).execute()

            for event in events_result.get("items", []):
                if event.get("status") == "cancelled":
                    continue

                start = event.get("start", {})
                end = event.get("end", {})

                if "date" in start:
                    start_dt = datetime.fromisoformat(start["date"])
                    end_dt = datetime.fromisoformat(end["date"])
                    all_day = True
                else:
                    start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
                    all_day = False

                events.append({
                    "id": event["id"],
                    "calendar_id": calendar_id,
                    "title": event.get("summary", "(No title)"),
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "all_day": all_day,
                    "location": event.get("location"),
                    "description": event.get("description"),
                    "color": event.get("colorId"),
                })
        except HttpError as e:
            print(f"Error fetching events from {calendar_id}: {e}")
            continue

    events.sort(key=lambda e: e["start"])
    return events
