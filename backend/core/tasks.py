from datetime import date

from django.tasks import task
from django.utils import timezone
from crontask import cron

from .models import Task, UserSettings
from .services.email import send_morning_reminder


@cron("0 * * * *")  # Every hour at minute 0
@task
def send_morning_emails():
    """
    Check all users and send morning reminder emails
    to those whose morning_email_time matches the current hour.
    """
    now = timezone.localtime()
    current_hour = now.hour

    # Find users with morning emails enabled and matching hour
    settings_to_notify = UserSettings.objects.filter(
        morning_email_enabled=True,
        morning_email_time__hour=current_hour,
    ).select_related("user")

    for user_settings in settings_to_notify:
        user = user_settings.user

        # Get today's tasks (due today or overdue, not completed)
        today = date.today()
        tasks = list(Task.objects.filter(
            user=user,
            completed=False,
            due_date__lte=today,
        ).order_by("due_date", "position"))

        if tasks:
            result = send_morning_reminder(user, tasks)
            if result:
                send_morning_emails.logger.info(
                    f"Sent morning email to {user.email} with {len(tasks)} tasks"
                )
        else:
            send_morning_emails.logger.info(
                f"No tasks for {user.email}, skipping email"
            )
