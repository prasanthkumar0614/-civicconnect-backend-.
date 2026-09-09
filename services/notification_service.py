"""
services/notification_service.py

Notifications triggered by the issue workflow, on two channels:
  - Email (existing) -- console backend in dev, real SMTP in production.
  - In-app (new) -- Notification rows shown in the dashboard's bell icon,
    for officers/admins. Citizens only get email (they don't use the
    authority dashboard).

Every send is wrapped in try/except: a failed notification must never
roll back the status change or complaint submission that triggered it,
the same "never block the real action" principle used in ai_service.py.
"""

import logging

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def _safe_send(subject: str, message: str, to: list[str]):
    if not to or not any(to):
        return
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to,
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 — deliberately broad, see module docstring
        logger.error("Notification send failed: %s", exc)


def _notify_inapp(recipients, message: str, issue=None):
    """Creates one Notification row per recipient User. Never raises."""
    if not recipients:
        return
    try:
        from issues.models import Notification  # local import avoids app-loading order issues
        Notification.objects.bulk_create([
            Notification(recipient=user, message=message, issue=issue)
            for user in recipients if user and user.pk
        ])
    except Exception as exc:  # noqa: BLE001
        logger.error("In-app notification failed: %s", exc)


def notify_issue_submitted(issue):
    """Confirms receipt to the citizen right after submission."""
    _safe_send(
        subject=f"CivicConnect — Report received: {issue.asset.asset_id}",
        message=(
            f"Hi {issue.reporter.username},\n\n"
            f"Your report on {issue.asset.asset_id} ({issue.asset.asset_type.name}) has been received "
            f"and logged as complaint #{issue.id}.\n\n"
            f"Description: {issue.description}\n\n"
            f"You can track its status any time in the CivicConnect app.\n\n"
            f"— CivicConnect"
        ),
        to=[issue.reporter.email],
    )


def notify_new_complaint(issue):
    """
    In-app "someone reported a new complaint" alert for the dashboard bell,
    sent to every Department Admin over the asset's department. Fires for
    EVERY new complaint, not just HIGH priority ones -- see
    notify_department_high_priority for the escalated (email+in-app) version.
    """
    department = issue.asset.department
    if not department:
        return
    admins = list(department.staff.filter(role="DEPT_ADMIN"))
    _notify_inapp(
        admins,
        message=f"New complaint on {issue.asset.asset_id} ({issue.asset.asset_type.name}) in {issue.asset.area.name}.",
        issue=issue,
    )


def notify_status_changed(issue, old_status: str):
    """Tells the citizen their complaint moved forward."""
    _safe_send(
        subject=f"CivicConnect — Update on complaint #{issue.id}: {issue.get_status_display()}",
        message=(
            f"Hi {issue.reporter.username},\n\n"
            f"Your complaint #{issue.id} on {issue.asset.asset_id} has moved from "
            f"{old_status} to {issue.status}.\n\n"
            + (f"Resolution notes: {issue.resolution_notes}\n\n" if issue.resolution_notes else "")
            + "— CivicConnect"
        ),
        to=[issue.reporter.email],
    )


def notify_officer_assigned(issue):
    """Tells the officer they've been handed a new complaint (email + in-app)."""
    officer = issue.assigned_officer
    if not officer:
        return
    _safe_send(
        subject=f"CivicConnect — New assignment: {issue.asset.asset_id}",
        message=(
            f"Hi {officer.username},\n\n"
            f"You've been assigned complaint #{issue.id} on {issue.asset.asset_id} "
            f"({issue.asset.asset_type.name}) in {issue.asset.area.name}.\n\n"
            f"Priority: {issue.ai_priority or 'Not yet triaged'}\n"
            f"Description: {issue.description}\n\n"
            f"— CivicConnect"
        ),
        to=[officer.email],
    )
    _notify_inapp(
        [officer],
        message=f"You were assigned complaint #{issue.id} on {issue.asset.asset_id}.",
        issue=issue,
    )


def notify_department_high_priority(issue):
    """
    Escalated alert (email + in-app) for HIGH priority issues -- these are
    safety-relevant (exposed wiring, traffic signal down, etc.) per the AI
    triage rules in ai_service.py, so they shouldn't sit unnoticed in a queue.
    """
    if issue.ai_priority != "HIGH" or not issue.asset.department:
        return
    admins = list(issue.asset.department.staff.filter(role="DEPT_ADMIN"))
    admin_emails = [a.email for a in admins]
    _safe_send(
        subject=f"CivicConnect — HIGH priority: {issue.asset.asset_id}",
        message=(
            f"A new HIGH priority complaint needs attention.\n\n"
            f"Asset: {issue.asset.asset_id} ({issue.asset.asset_type.name})\n"
            f"Area: {issue.asset.area.name}\n"
            f"Summary: {issue.ai_summary or issue.description}\n\n"
            f"— CivicConnect"
        ),
        to=admin_emails,
    )
    _notify_inapp(
        admins,
        message=f"HIGH PRIORITY: {issue.asset.asset_id} — {issue.ai_summary or issue.description}",
        issue=issue,
    )


def notify_cluster_detected(department, cluster_assets):
    """
    Called when the map/clustering endpoint (assets/clustering.py) finds
    a new group of nearby faulty assets -- surfaces the "possible larger
    fault" signal to the department, not just on the map.
    """
    if not department:
        return
    admins = list(department.staff.filter(role="DEPT_ADMIN"))
    admin_emails = [a.email for a in admins]
    asset_list = ", ".join(a.asset_id for a in cluster_assets)
    _safe_send(
        subject=f"CivicConnect — Possible shared fault: {len(cluster_assets)} nearby assets",
        message=(
            f"{len(cluster_assets)} nearby assets currently have open complaints at the same time: "
            f"{asset_list}.\n\n"
            f"This pattern often indicates one shared cause (e.g. a transformer fault) rather than "
            f"separate unrelated issues. View the asset map for details.\n\n"
            f"— CivicConnect"
        ),
        to=admin_emails,
    )
    _notify_inapp(
        admins,
        message=f"Possible shared fault across {len(cluster_assets)} nearby assets: {asset_list}.",
    )


# ---------------------------------------------------------------------------
# Settings needed (add to config/settings_additions.py):
#
# DEFAULT_FROM_EMAIL = "noreply@civicconnect.local"
#
# if DEBUG:
#     EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# else:
#     EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
#     EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
#     EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
#     EMAIL_USE_TLS = True
#     EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
#     EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
# ---------------------------------------------------------------------------