import pytest
from django.db import IntegrityError, transaction

from apps.insights.models import InsightSnapshot
from apps.insights.tests.factories import InsightSnapshotFactory
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def test_one_snapshot_per_org_per_day():
    snap = InsightSnapshotFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        InsightSnapshotFactory(organisation=snap.organisation, computed_for=snap.computed_for)


def test_same_day_different_org_allowed():
    snap = InsightSnapshotFactory()
    InsightSnapshotFactory(organisation=OrganisationFactory(), computed_for=snap.computed_for)
    assert InsightSnapshot.objects.count() == 2


def test_latest_index_exists():
    idx = [(i.fields) for i in InsightSnapshot._meta.indexes]
    assert ["organisation", "-computed_for"] in idx
