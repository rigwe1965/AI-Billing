"""Pluggable alert notification channels.

v1 decision (confirmed with the user): in-app notifications only. The Alert
row itself, surfaced via GET /api/alerts, IS the in-app notification -- there
is nothing extra to "send" for that channel. EmailNotificationChannel is a
stub showing where a real provider (SMTP/SendGrid/SES) plugs in later as a
config change, not a rearchitecture -- it deliberately is not wired up.
"""

from typing import Protocol

from app.models.budget import Alert
from app.models.department import Department


class NotificationChannel(Protocol):
    name: str

    def send(self, alert: Alert, department: Department) -> None:
        ...


class InAppNotificationChannel:
    name = "in_app"

    def send(self, alert: Alert, department: Department) -> None:
        # No-op: the Alert row already persisted is the in-app notification.
        pass


class EmailNotificationChannel:
    """Not wired to a real provider in v1. Raising here (rather than silently
    no-op'ing) makes it obvious at call time if something ever enables this
    channel before a real provider is configured."""

    name = "email"

    def send(self, alert: Alert, department: Department) -> None:
        raise NotImplementedError(
            "Email notifications are not configured in this deployment. "
            "The alert is still recorded and visible via GET /api/alerts."
        )


ACTIVE_CHANNELS: list[NotificationChannel] = [InAppNotificationChannel()]


def dispatch(alert: Alert, department: Department) -> list[str]:
    """Sends `alert` through every active channel, returning the names of
    channels that succeeded (used to populate Alert.notified_via)."""
    sent_via = []
    for channel in ACTIVE_CHANNELS:
        channel.send(alert, department)
        sent_via.append(channel.name)
    return sent_via
