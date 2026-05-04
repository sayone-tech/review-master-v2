import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.organisations.tests.factories import OrganisationFactory


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    organisation = factory.SubFactory(OrganisationFactory)
    recipient = factory.SubFactory(UserFactory)
    notification_type = Notification.NotificationType.NEW_REVIEW
    title = factory.Sequence(lambda n: f"Notification {n}")
    target_url = "/admin/org/reviews/"
    is_read = False
