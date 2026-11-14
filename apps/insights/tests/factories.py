import datetime

import factory
from factory.django import DjangoModelFactory

from apps.insights.models import InsightSnapshot
from apps.organisations.tests.factories import OrganisationFactory


class InsightSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = InsightSnapshot

    organisation = factory.SubFactory(OrganisationFactory)
    computed_for = factory.LazyFunction(datetime.date.today)
    window_from = factory.LazyAttribute(lambda o: o.computed_for - datetime.timedelta(days=90))
    window_to = factory.LazyAttribute(lambda o: o.computed_for)
    payload = factory.LazyFunction(dict)
