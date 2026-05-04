import pytest

from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.django_db
def test_create_notification_defaults() -> None:
    notification = NotificationFactory()
    assert notification.pk is not None
    assert notification.is_read is False
    assert notification.notification_type == Notification.NotificationType.NEW_REVIEW
    assert notification.target_url == "/admin/org/reviews/"


@pytest.mark.django_db
def test_notification_str() -> None:
    notification = NotificationFactory(
        notification_type=Notification.NotificationType.NEW_ACTION_ITEM,
    )
    rendered = str(notification)
    assert "new_action_item" in rendered
    assert str(notification.recipient_id) in rendered


@pytest.mark.django_db
def test_default_ordering_newest_first() -> None:
    n1 = NotificationFactory()
    n2 = NotificationFactory()
    n3 = NotificationFactory()
    ordered = list(Notification.objects.all())
    assert ordered[0].pk == n3.pk
    assert ordered[1].pk == n2.pk
    assert ordered[2].pk == n1.pk


@pytest.mark.django_db
def test_nullable_fks() -> None:
    notification = NotificationFactory(shop=None, action_item=None, review=None)
    notification.refresh_from_db()
    assert notification.shop is None
    assert notification.action_item is None
    assert notification.review is None
