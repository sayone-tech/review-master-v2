"""Ranking, daily snapshot build, retention, task and Beat seeding."""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.insights.models import InsightSnapshot
from apps.insights.services import build as build_module
from apps.insights.services.build import build_snapshot, compute_all_insights, rank
from apps.insights.services.rules import Candidate
from apps.insights.tasks import compute_daily_insights_task
from apps.insights.tests.factories import InsightSnapshotFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 11, 14)


def cand(type_=4, chapter="attention", score=1.0, review_count=1, **kw) -> Candidate:
    base = {
        "type": type_,
        "chapter": chapter,
        "score": score,
        "headline": "h",
        "title": "t",
        "body": "b",
        "visual": {},
        "link": {},
        "store_id": None,
        "tag_text": None,
        "review_count": review_count,
        "cta": "c",
        "caption": "cap",
    }
    base.update(kw)
    return Candidate(**base)


def test_rank_attention_before_good_then_score_desc():
    out = rank(
        [
            cand(4, "good", 9.0),
            cand(4, "attention", 1.0),
            cand(5, "attention", 2.0),
            cand(6, "good", 10.0),
        ]
    )
    assert [(c.chapter, c.score) for c in out] == [
        ("attention", 2.0),
        ("attention", 1.0),
        ("good", 10.0),
        ("good", 9.0),
    ]


def test_rank_type_weight_leads_waiting_and_complaint():
    out = rank([cand(4, score=1.0), cand(2, score=1.0), cand(1, score=1.0), cand(3, score=1.0)])
    assert [c.type for c in out] == [2, 1, 3, 4]


def test_rank_ties_higher_review_count_first():
    out = rank([cand(4, review_count=3), cand(5, review_count=9)])
    assert [c.review_count for c in out] == [9, 3]


def test_rank_max_two_per_type_keeps_best():
    out = rank([cand(4, score=s, headline=str(s)) for s in (1, 2, 3, 4)])
    assert [c.headline for c in out] == ["4", "3"]


def test_rank_max_eight_total():
    items = [cand(t, score=1.0) for t in range(1, 9) for _ in range(2)]
    out = rank(items)
    assert len(out) == 8


def test_rank_does_not_mutate_score():
    c = cand(2, score=1.0)
    assert rank([c])[0].score == 1.0


def test_build_snapshot_empty_org():
    org = OrganisationFactory()
    snap = build_snapshot(organisation_id=org.pk, today=TODAY)
    assert snap.payload == {
        "cover": {"reviews": 0, "stores": 0, "attention": 0, "good": 0},
        "items": [],
    }
    assert (snap.window_from, snap.window_to) == (
        TODAY - dt.timedelta(days=30),
        TODAY - dt.timedelta(days=1),
    )
    assert snap.computed_for == TODAY


def test_build_snapshot_cover_counts_and_items(monkeypatch):
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    ShopFactory(organisation=org, is_active=False)
    when = timezone.make_aware(dt.datetime.combine(TODAY - dt.timedelta(days=5), dt.time(12)))
    ReviewFactory(organisation=org, shop=shop, review_create_time=when)
    ReviewFactory(organisation=org, shop=shop, review_create_time=when, deleted_at=when)
    items = [cand(4, "attention", 2.0), cand(5, "good", 1.0), cand(6, "good", 0.5)]
    monkeypatch.setattr("apps.insights.services.build.collect_candidates", lambda **kw: items)
    snap = build_snapshot(organisation_id=org.pk, today=TODAY)
    assert snap.payload["cover"] == {"reviews": 1, "stores": 1, "attention": 1, "good": 2}
    assert snap.payload["items"][0] == dataclasses.asdict(items[0])
    assert len(snap.payload["items"]) == 3


def test_build_snapshot_idempotent_same_day(monkeypatch):
    org = OrganisationFactory()
    monkeypatch.setattr("apps.insights.services.build.collect_candidates", lambda **kw: [])
    first = build_snapshot(organisation_id=org.pk, today=TODAY)
    monkeypatch.setattr("apps.insights.services.build.collect_candidates", lambda **kw: [cand(4)])
    second = build_snapshot(organisation_id=org.pk, today=TODAY)
    assert first.pk == second.pk
    assert InsightSnapshot.objects.filter(organisation=org).count() == 1
    assert len(second.payload["items"]) == 1


def test_build_snapshot_retention_is_per_org_14_days():
    org, other = OrganisationFactory(), OrganisationFactory()
    old = InsightSnapshotFactory(organisation=org, computed_for=TODAY - dt.timedelta(days=15))
    edge = InsightSnapshotFactory(organisation=org, computed_for=TODAY - dt.timedelta(days=14))
    other_old = InsightSnapshotFactory(
        organisation=other, computed_for=TODAY - dt.timedelta(days=30)
    )
    build_snapshot(organisation_id=org.pk, today=TODAY)
    assert not InsightSnapshot.objects.filter(pk=old.pk).exists()
    assert InsightSnapshot.objects.filter(pk=edge.pk).exists()
    assert InsightSnapshot.objects.filter(pk=other_old.pk).exists()


def test_compute_all_insights_only_orgs_with_active_shop():
    with_shop = OrganisationFactory()
    ShopFactory(organisation=with_shop)
    inactive_only = OrganisationFactory()
    ShopFactory(organisation=inactive_only, is_active=False)
    OrganisationFactory()
    assert compute_all_insights() == 1
    assert InsightSnapshot.objects.filter(organisation=with_shop).exists()
    assert InsightSnapshot.objects.count() == 1


def test_task_runs_service():
    org = OrganisationFactory()
    ShopFactory(organisation=org)
    compute_daily_insights_task.delay()
    assert InsightSnapshot.objects.filter(organisation=org).count() == 1


def test_beat_row_seeded():
    pt = PeriodicTask.objects.get(name="insights_compute_daily")
    assert pt.task == "apps.insights.tasks.compute_daily_insights_task"
    assert pt.queue == "default"
    assert (pt.crontab.minute, pt.crontab.hour) == ("0", "2")
    assert pt.enabled


def test_compute_all_insights_isolates_failing_org(monkeypatch):
    first, second = OrganisationFactory(), OrganisationFactory()
    ShopFactory(organisation=first)
    ShopFactory(organisation=second)
    real = build_module.collect_candidates

    def flaky(*, organisation_id, window):
        if organisation_id == first.pk:
            raise ValueError("boom")
        return real(organisation_id=organisation_id, window=window)

    monkeypatch.setattr(build_module, "collect_candidates", flaky)
    with pytest.raises(RuntimeError, match=str(first.pk)):
        compute_all_insights()
    assert InsightSnapshot.objects.filter(organisation=second).exists()
    assert not InsightSnapshot.objects.filter(organisation=first).exists()


def test_build_snapshot_end_to_end_round_trips_json():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    other = ShopFactory(organisation=org)
    for d in (12, 8, 4):
        when = timezone.make_aware(dt.datetime.combine(TODAY - dt.timedelta(days=d), dt.time(12)))
        ReviewFactory(organisation=org, shop=shop, review_create_time=when, sentiment="negative")
    when = timezone.make_aware(dt.datetime.combine(TODAY - dt.timedelta(days=3), dt.time(9)))
    for _ in range(10):
        ReviewFactory(organisation=org, shop=shop, review_create_time=when, star_rating=1)
        ReviewFactory(organisation=org, shop=other, review_create_time=when, star_rating=5)
    snap = build_snapshot(organisation_id=org.pk, today=TODAY)
    snap = InsightSnapshot.objects.get(pk=snap.pk)
    items = snap.payload["items"]
    assert len(items) >= 2
    fields = {f.name for f in dataclasses.fields(Candidate)}
    assert all(set(i) == fields for i in items)
    assert snap.payload["cover"]["attention"] + snap.payload["cover"]["good"] == len(items)
    assert {i["type"] for i in items} >= {2, 3}
