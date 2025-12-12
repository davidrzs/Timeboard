import resend
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY


def send_email(to: str, subject: str, html: str) -> dict | None:
    """Send an email via Resend."""
    if not settings.RESEND_API_KEY:
        print(f"[Email] RESEND_API_KEY not set, skipping email to {to}")
        return None

    try:
        response = resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to,
            "subject": subject,
            "html": html,
        })
        return response
    except Exception as e:
        print(f"[Email] Failed to send to {to}: {e}")
        return None


def send_morning_reminder(user, tasks: list) -> dict | None:
    """Send morning task reminder email with scheduled plan."""
    if not tasks:
        return None

    # Generate plan using deterministic scheduler
    plan = None
    try:
        from .llm import generate_deterministic_plan
        plan = generate_deterministic_plan(user)
    except Exception as e:
        print(f"[Email] Plan generation failed for {user.email}: {e}")

    if plan:
        # Get task titles from the database
        task_ids = [slot.task_id for slot in plan.schedule]
        from ..models import Task
        tasks_by_id = {t.id: t for t in Task.objects.filter(id__in=task_ids)}

        def calc_end_time(start: str, minutes: int) -> str:
            h, m = map(int, start.split(':'))
            total = h * 60 + m + minutes
            return f"{total // 60:02d}:{total % 60:02d}"

        # Build schedule HTML
        schedule_html = "".join(
            f'''<tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 12px 0; color: #6b7280; font-family: monospace; width: 100px;">{slot.start_time} - {calc_end_time(slot.start_time, slot.estimated_minutes)}</td>
                <td style="padding: 12px 8px;">
                    <div style="font-weight: 500; color: #1f2937;">{tasks_by_id.get(slot.task_id, type("", (), {"title": f"Task #{slot.task_id}"})).title}</div>
                </td>
                <td style="padding: 12px 0; color: #9ca3af; font-size: 12px; text-align: right;">{slot.estimated_minutes}min</td>
            </tr>'''
            for slot in plan.schedule
        )

        html = f"""
        <div style="font-family: system-ui, sans-serif; max-width: 600px;">
            <p style="color: #374151; margin-bottom: 20px;">{plan.message}</p>

            <h3 style="color: #374151; font-size: 14px; margin-bottom: 12px;">Today's Schedule</h3>
            <table style="width: 100%; border-collapse: collapse;">
                {schedule_html}
            </table>

            <p style="margin-top: 24px;">
                <a href="{settings.FRONTEND_URL}" style="display: inline-block; background: #1f2937; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 14px;">Open Timeboard</a>
            </p>
        </div>
        """

        return send_email(
            to=user.email,
            subject=f"Your daily plan ({len(plan.schedule)} tasks)",
            html=html,
        )

    # Fallback to simple list if LLM fails
    task_list = "".join(
        f'<li style="margin-bottom: 8px;">{t.title}'
        f'{f" ({t.estimated_minutes}min)" if t.estimated_minutes else ""}</li>'
        for t in tasks
    )

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 500px;">
        <h2 style="color: #1f2937; margin-bottom: 16px;">Good morning!</h2>
        <p style="color: #4b5563; margin-bottom: 16px;">
            Here are your tasks for today:
        </p>
        <ul style="color: #1f2937; padding-left: 20px;">
            {task_list}
        </ul>
        <p style="color: #9ca3af; font-size: 14px; margin-top: 24px;">
            <a href="{settings.FRONTEND_URL}" style="color: #3b82f6;">Open Timeboard</a>
        </p>
    </div>
    """

    return send_email(
        to=user.email,
        subject=f"Your tasks for today ({len(tasks)} items)",
        html=html,
    )
