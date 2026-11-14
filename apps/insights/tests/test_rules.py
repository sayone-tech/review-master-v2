"""Insight rule functions (types 1-8): thresholds, copy, visuals, links, scoping, query counts.

The core contract: every number an insight shows equals what its link shows on the
Reviews page. ``test_review_count_matches_reviews_page_link`` checks that by running the
Reviews page's own FilterSet with each candidate's link.
"""

from __future__ import annotations

import datetime as dt
import itertools
from collections.abc import Callable

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.insights.services import rules
from apps.insights.services.rules import Candidate, mention_q
from apps.insights.services.windows import Window, six_windows, windows_for
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.filters import ReviewFilterSet
from apps.reviews.models import Review
from apps.reviews.selectors.reviews import base_reviews_queryset
from apps.reviews.tests.factories import OrgCanonicalTagFactory, ReviewFactory, ReviewTagFactory
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 11, 14)
W = windows_for(TODAY)
UTC = dt.UTC


def at(day: dt.date, hour: int = 12, minute: int = 0, second: int = 0, micro: int = 0):
    return dt.datetime(day.year, day.month, day.day, hour, minute, second, micro, tzinfo=UTC)


def in_now(offset: int = 5) -> dt.datetime:
    return at(W.now_from + dt.timedelta(days=offset))


def in_before(offset: int = 5) -> dt.datetime:
    return at(W.before_from + dt.timedelta(days=offset))


def in_window(index: int, offset: int = 5) -> dt.datetime:
    """A moment inside 30-day window ``index`` (0 = oldest, 5 = now)."""
    w_from, _ = six_windows(W)[index]
    return at(w_from + dt.timedelta(days=offset))


def mk(shop: Shop, when: dt.datetime, n: int = 1, **kw) -> list[Review]:
    return [
        ReviewFactory(organisation=shop.organisation, shop=shop, review_create_time=when, **kw)
        for _ in range(n)
    ]


def tagged(shop: Shop, when: dt.datetime, label: str, n: int = 1, canonical=None, **kw):
    out = []
    for r in mk(shop, when, n, **kw):
        ReviewTagFactory(review=r, label=label, polarity="negative", canonical_tag=canonical)
        out.append(r)
    return out


def link_count(org_id: int, link: dict) -> int:
    """Count what the Reviews page shows for this link (its own FilterSet + base queryset)."""
    mapping = {
        "store": "shop",
        "tags": "tags",
        "sentiment": "sentiment",
        "rating": "rating",
        "replied": "is_replied",
        "from": "from_date",
        "to": "to_date",
    }
    data = {mapping[k]: str(v) for k, v in link.items()}
    fs = ReviewFilterSet(data, queryset=base_reviews_queryset(organisation_id=org_id))
    assert fs.is_valid(), fs.errors
    return fs.qs.count()


# --------------------------------------------------------------------------- windows


def test_windows_for_is_thirty_full_days_ending_yesterday():
    assert windows_for(TODAY) == Window(
        now_from=dt.date(2026, 10, 15),
        now_to=dt.date(2026, 11, 13),
        before_from=dt.date(2026, 9, 15),
        before_to=dt.date(2026, 10, 14),
    )


def test_six_windows_are_consecutive_oldest_first_ending_with_now():
    ws = six_windows(W)
    assert len(ws) == 6
    assert ws[5] == (W.now_from, W.now_to)
    assert ws[4] == (W.before_from, W.before_to)
    for (a_from, a_to), (b_from, _b_to) in itertools.pairwise(ws):
        assert (a_to - a_from).days == 29
        assert b_from == a_to + dt.timedelta(days=1)


# --------------------------------------------------------------------------- type 1


@pytest.fixture
def wait_tag_shop():
    shop = ShopFactory(name="Kochi")
    tag = OrgCanonicalTagFactory(organisation=shop.organisation, label="Wait time")
    return shop, tag


def test_complaint_rising_fires_at_threshold(wait_tag_shop):
    shop, _ = wait_tag_shop
    tagged(shop, in_now(), "wait time", n=5, sentiment="negative")
    tagged(shop, in_before(), "wait time", n=2, sentiment="negative")

    [c] = rules.complaint_rising(organisation_id=shop.organisation_id, window=W)

    assert c.type == 1
    assert c.chapter == "attention"
    assert c.headline == "2.5\u00d7"
    assert c.title == "{tag} complaints doubled at {store}"
    assert c.body == "5 reviews mentioned {tag_lower} in the last 30 days, up from 2."
    assert c.visual == {"kind": "before_now", "before": 2, "now": 5}
    assert c.link == {
        "store": shop.id,
        "tags": "Wait time",
        "sentiment": "negative",
        "from": "2026-10-15",
        "to": "2026-11-13",
    }
    assert c.store_id == shop.id
    assert c.tag_text == "Wait time"
    assert c.review_count == 5
    assert c.cta == "See reviews"
    assert c.caption == "Negative reviews mentioning {tag_lower} at {store}"


def test_complaint_rising_not_below_now_minimum(wait_tag_shop):
    shop, _ = wait_tag_shop
    tagged(shop, in_now(), "wait time", n=4, sentiment="negative")
    tagged(shop, in_before(), "wait time", n=2, sentiment="negative")
    assert rules.complaint_rising(organisation_id=shop.organisation_id, window=W) == []


def test_complaint_rising_not_below_double(wait_tag_shop):
    shop, _ = wait_tag_shop
    tagged(shop, in_now(), "wait time", n=5, sentiment="negative")
    tagged(shop, in_before(), "wait time", n=3, sentiment="negative")
    assert rules.complaint_rising(organisation_id=shop.organisation_id, window=W) == []


def test_complaint_rising_tripled_and_from_zero_copy(wait_tag_shop):
    shop, _ = wait_tag_shop
    tagged(shop, in_now(), "wait time", n=6, sentiment="negative")
    tagged(shop, in_before(), "wait time", n=2, sentiment="negative")
    [c] = rules.complaint_rising(organisation_id=shop.organisation_id, window=W)
    assert c.headline == "3\u00d7"
    assert c.title == "{tag} complaints tripled at {store}"

    # ratio >= 4: not "tripled"; title repeats the headline's rounded ratio
    quad = ShopFactory(organisation=shop.organisation, name="Quad")
    tagged(quad, in_now(), "wait time", n=9, sentiment="negative")
    tagged(quad, in_before(), "wait time", n=2, sentiment="negative")
    by_store = {
        x.store_id: x
        for x in rules.complaint_rising(organisation_id=shop.organisation_id, window=W)
    }
    assert by_store[quad.id].headline == "4.5\u00d7"
    assert by_store[quad.id].title == "{tag} complaints rose 4.5\u00d7 at {store}"

    other = ShopFactory(organisation=shop.organisation, name="Other")
    tagged(other, in_now(), "wait time", n=5, sentiment="negative")
    by_store = {
        x.store_id: x
        for x in rules.complaint_rising(organisation_id=shop.organisation_id, window=W)
    }
    fresh = by_store[other.id]
    assert fresh.headline == "5"
    assert fresh.title == "New {tag} complaints at {store}"
    assert fresh.body == (
        "5 reviews mentioned {tag_lower} in the last 30 days, none in the 30 days before."
    )


def test_complaint_rising_ignores_non_negative_sentiment(wait_tag_shop):
    shop, _ = wait_tag_shop
    tagged(shop, in_now(), "wait time", n=4, sentiment="negative")
    tagged(shop, in_now(), "wait time", n=3, sentiment="positive")
    assert rules.complaint_rising(organisation_id=shop.organisation_id, window=W) == []


def test_mention_matches_raw_label_or_canonical_label_counted_once(wait_tag_shop):
    shop, tag = wait_tag_shop
    # "long wait" mapped to canonical "Wait time" counts for "Wait time".
    tagged(shop, in_now(), "long wait", n=3, canonical=tag, sentiment="negative")
    # A raw label equal to the canonical label (any case) also counts.
    tagged(shop, in_now(), "WAIT TIME", n=1, sentiment="negative")
    # Two matching tags on one review count once.
    [r] = tagged(shop, in_now(), "wait time", n=1, sentiment="negative")
    ReviewTagFactory(review=r, label="slow queue", polarity="negative", canonical_tag=tag)

    [c] = rules.complaint_rising(organisation_id=shop.organisation_id, window=W)
    assert c.review_count == 5
    # Same rule as the mention_q helper (the Reviews tag filter after Task 5).
    assert Review.objects.filter(mention_q("Wait time")).count() == 5


# --------------------------------------------------------------------------- type 2


def test_waiting_negative_fires_at_three():
    shop = ShopFactory()
    mk(shop, at(TODAY - dt.timedelta(days=12)), sentiment="negative")
    mk(shop, at(TODAY - dt.timedelta(days=4)), n=2, sentiment="negative")
    mk(shop, in_now(), sentiment="negative", is_replied=True)
    mk(shop, in_now(), sentiment="positive")

    [c] = rules.waiting_negative(organisation_id=shop.organisation_id, window=W)

    assert c.type == 2
    assert c.chapter == "attention"
    assert c.headline == "3"
    assert c.title == "3 negative reviews are waiting for a reply"
    assert c.body == (
        "3 negative reviews from the last 30 days have no reply yet. The oldest has waited 12 days."
    )
    assert c.visual == {"kind": "waiting_days", "days": [12, 4, 4]}
    assert c.link == {
        "sentiment": "negative",
        "replied": "false",
        "from": "2026-10-15",
        "to": "2026-11-13",
    }
    assert c.store_id is None
    assert c.tag_text is None
    assert c.review_count == 3
    assert c.cta == "Reply now"


def test_waiting_negative_not_at_two():
    shop = ShopFactory()
    mk(shop, in_now(), n=2, sentiment="negative")
    assert rules.waiting_negative(organisation_id=shop.organisation_id, window=W) == []


def test_waiting_negative_visual_caps_at_ten_oldest_first():
    shop = ShopFactory()
    for d in range(1, 13):
        mk(shop, at(TODAY - dt.timedelta(days=d + 1)), sentiment="negative")
    [c] = rules.waiting_negative(organisation_id=shop.organisation_id, window=W)
    assert c.headline == "12"
    assert c.visual["days"] == [13, 12, 11, 10, 9, 8, 7, 6, 5, 4]


# --------------------------------------------------------------------------- type 3


def test_store_below_brand_fires_at_half_star():
    org = OrganisationFactory()
    low = ShopFactory(organisation=org)
    high = ShopFactory(organisation=org)
    mk(low, in_now(), n=10, star_rating=4)
    mk(high, in_now(), n=10, star_rating=5)

    [c] = rules.store_below_brand(organisation_id=org.id, window=W)

    assert c.type == 3
    assert c.chapter == "attention"
    assert c.headline == "\u22120.5★"
    assert c.title == "{store} is rated below your brand"
    assert c.body == (
        "{store} averaged 4.0★ from 10 reviews in the last 30 days, against 4.5★ across all stores."
    )
    assert c.visual == {"kind": "rating_line", "store": 4.0, "brand": 4.5}
    assert c.link == {"store": low.id, "from": "2026-10-15", "to": "2026-11-13"}
    assert c.store_id == low.id
    assert c.review_count == 10


def test_store_below_brand_not_below_gap():
    org = OrganisationFactory()
    low = ShopFactory(organisation=org)
    high = ShopFactory(organisation=org)
    mk(low, in_now(), n=9, star_rating=4)
    mk(low, in_now(), n=1, star_rating=5)  # 4.1 vs brand 4.55 -> gap 0.45
    mk(high, in_now(), n=10, star_rating=5)
    assert rules.store_below_brand(organisation_id=org.id, window=W) == []


def test_store_below_brand_needs_ten_reviews():
    org = OrganisationFactory()
    low = ShopFactory(organisation=org)
    high = ShopFactory(organisation=org)
    mk(low, in_now(), n=9, star_rating=1)
    mk(high, in_now(), n=10, star_rating=5)
    assert rules.store_below_brand(organisation_id=org.id, window=W) == []


# --------------------------------------------------------------------------- type 4


def test_five_star_share_up_fires_at_ten_points():
    shop = ShopFactory()
    mk(shop, in_now(), n=6, star_rating=5)
    mk(shop, in_now(), n=4, star_rating=3)
    mk(shop, in_before(), n=5, star_rating=5)
    mk(shop, in_before(), n=5, star_rating=3)

    [c] = rules.five_star_share_change(organisation_id=shop.organisation_id, window=W)

    assert c.type == 4
    assert c.chapter == "good"
    assert c.headline == "60%"
    assert c.title == "More 5-star reviews at {store}"
    assert c.body == "60% of reviews were 5-star in the last 30 days, up from 50%."
    assert c.visual == {
        "kind": "share_line",
        "points": [None, None, None, None, 50.0, 60.0],
    }
    assert c.link == {"store": shop.id, "rating": 5, "from": "2026-10-15", "to": "2026-11-13"}
    assert c.review_count == 6


def test_five_star_share_down_is_attention():
    shop = ShopFactory()
    mk(shop, in_now(), n=4, star_rating=5)
    mk(shop, in_now(), n=6, star_rating=3)
    mk(shop, in_before(), n=5, star_rating=5)
    mk(shop, in_before(), n=5, star_rating=3)
    [c] = rules.five_star_share_change(organisation_id=shop.organisation_id, window=W)
    assert c.chapter == "attention"
    assert c.headline == "40%"
    assert c.title == "Fewer 5-star reviews at {store}"
    assert c.body == "40% of reviews were 5-star in the last 30 days, down from 50%."
    assert c.link["rating"] == 5


def test_five_star_share_not_below_ten_points():
    shop = ShopFactory()
    mk(shop, in_now(), n=6, star_rating=5)
    mk(shop, in_now(), n=4, star_rating=3)
    mk(shop, in_before(), n=6, star_rating=5)  # 6/11 = 54.5% -> +5.5 points
    mk(shop, in_before(), n=5, star_rating=3)
    assert rules.five_star_share_change(organisation_id=shop.organisation_id, window=W) == []


def test_five_star_share_needs_ten_in_both_windows():
    shop = ShopFactory()
    mk(shop, in_now(), n=10, star_rating=5)
    mk(shop, in_before(), n=9, star_rating=3)
    assert rules.five_star_share_change(organisation_id=shop.organisation_id, window=W) == []


# --------------------------------------------------------------------------- type 5


def test_reply_rate_up_fires_at_ten_points():
    shop = ShopFactory()
    mk(shop, in_now(), n=12, is_replied=True)
    mk(shop, in_now(), n=8)
    mk(shop, in_before(), n=10, is_replied=True)
    mk(shop, in_before(), n=10)

    [c] = rules.reply_rate_change(organisation_id=shop.organisation_id, window=W)

    assert c.type == 5
    assert c.chapter == "good"
    assert c.headline == "60%"
    assert c.title == "Your reply rate rose to 60%"
    assert c.body == (
        "You replied to 12 of 20 reviews from the last 30 days, up from 50% in the 30 days before."
    )
    assert c.visual == {"kind": "progress", "before": 50, "now": 60}
    assert c.link == {"from": "2026-10-15", "to": "2026-11-13"}
    assert c.store_id is None
    assert c.review_count == 20
    assert c.cta == "See replies"


def test_reply_rate_down_links_to_not_replied():
    shop = ShopFactory()
    mk(shop, in_now(), n=8, is_replied=True)
    mk(shop, in_now(), n=12)
    mk(shop, in_before(), n=10, is_replied=True)
    mk(shop, in_before(), n=10)
    [c] = rules.reply_rate_change(organisation_id=shop.organisation_id, window=W)
    assert c.chapter == "attention"
    assert c.headline == "40%"
    assert c.title == "Your reply rate fell to 40%"
    assert c.link == {"replied": "false", "from": "2026-10-15", "to": "2026-11-13"}
    assert c.review_count == 12
    assert c.cta == "See reviews"


def test_reply_rate_not_below_ten_points_or_twenty_reviews():
    shop = ShopFactory()
    mk(shop, in_now(), n=11, is_replied=True)  # 55% vs 50%
    mk(shop, in_now(), n=9)
    mk(shop, in_before(), n=10, is_replied=True)
    mk(shop, in_before(), n=10)
    assert rules.reply_rate_change(organisation_id=shop.organisation_id, window=W) == []

    small = ShopFactory()
    mk(small, in_now(), n=19, is_replied=True)
    mk(small, in_before(), n=20)
    assert rules.reply_rate_change(organisation_id=small.organisation_id, window=W) == []


# --------------------------------------------------------------------------- type 6


def _three_good_windows(shop: Shop, now_ratings: list[int]) -> None:
    for r in now_ratings:
        mk(shop, in_window(5), star_rating=r)
    mk(shop, in_window(4), n=10, star_rating=4)  # 4.0
    mk(shop, in_window(3), n=2, star_rating=5)  # 4.2
    mk(shop, in_window(3), n=8, star_rating=4)


def test_best_month_fires_with_three_qualifying_windows():
    shop = ShopFactory()
    _three_good_windows(shop, [5] * 5 + [4] * 5)  # 4.5
    mk(shop, in_window(1), n=3, star_rating=1)  # thin window: shown, not qualifying

    [c] = rules.best_month(organisation_id=shop.organisation_id, window=W)

    assert c.type == 6
    assert c.chapter == "good"
    assert c.headline == "4.5★"
    assert c.title == "{store} had its best month in six months"
    assert c.body == (
        "{store} averaged 4.5★ from 10 reviews in the last 30 days, "
        "its highest in six months (previous best 4.2★)."
    )
    assert c.visual == {
        "kind": "monthly_bars",
        "points": [None, 1.0, None, 4.2, 4.0, 4.5],
    }
    assert c.link == {"store": shop.id, "from": "2026-10-15", "to": "2026-11-13"}
    assert c.review_count == 10


def test_best_month_needs_three_qualifying_windows():
    shop = ShopFactory()
    mk(shop, in_window(5), n=10, star_rating=5)
    mk(shop, in_window(4), n=10, star_rating=4)
    mk(shop, in_window(3), n=9, star_rating=4)
    assert rules.best_month(organisation_id=shop.organisation_id, window=W) == []


def test_best_month_tie_is_not_best():
    shop = ShopFactory()
    _three_good_windows(shop, [5] * 2 + [4] * 8)  # 4.2 == previous best
    assert rules.best_month(organisation_id=shop.organisation_id, window=W) == []


# --------------------------------------------------------------------------- type 7


def test_new_tag_fires_at_five_mentions():
    org = OrganisationFactory()
    a = ShopFactory(organisation=org)
    b = ShopFactory(organisation=org)
    OrgCanonicalTagFactory(organisation=org, label="Parking")
    tagged(a, in_now(), "parking", n=3, sentiment="positive")
    tagged(b, in_now(), "parking", n=2, sentiment="negative")
    tagged(a, at(W.now_from - dt.timedelta(days=200)), "parking", sentiment="negative")

    [c] = rules.new_tag(organisation_id=org.id, window=W)

    assert c.type == 7
    assert c.chapter == "good"
    assert c.headline == "5"
    assert c.title == "{tag} is a new topic in your reviews"
    assert c.body == (
        "5 reviews mentioned {tag_lower} in the last 30 days, and none in the five months before."
    )
    assert c.visual == {
        "kind": "store_bars",
        "items": [{"store_id": a.id, "count": 3}, {"store_id": b.id, "count": 2}],
    }
    assert c.link == {"tags": "Parking", "from": "2026-10-15", "to": "2026-11-13"}
    assert c.store_id is None
    assert c.tag_text == "Parking"
    assert c.review_count == 5
    assert c.caption == "Reviews mentioning {tag_lower} per store"


def test_new_tag_mostly_negative_is_attention():
    shop = ShopFactory()
    OrgCanonicalTagFactory(organisation=shop.organisation, label="Parking")
    tagged(shop, in_now(), "parking", n=3, sentiment="negative")
    tagged(shop, in_now(), "parking", n=2, sentiment="positive")
    [c] = rules.new_tag(organisation_id=shop.organisation_id, window=W)
    assert c.chapter == "attention"


def test_new_tag_not_at_four_or_when_seen_in_last_six_months():
    shop = ShopFactory()
    OrgCanonicalTagFactory(organisation=shop.organisation, label="Parking")
    tagged(shop, in_now(), "parking", n=4)
    assert rules.new_tag(organisation_id=shop.organisation_id, window=W) == []

    tagged(shop, in_now(), "parking", n=1)
    tagged(shop, in_window(0), "parking", n=1)
    assert rules.new_tag(organisation_id=shop.organisation_id, window=W) == []


# --------------------------------------------------------------------------- type 8


def test_volume_drop_fires_at_half():
    shop = ShopFactory()
    mk(shop, in_before(), n=10)
    mk(shop, in_now(), n=5)

    [c] = rules.volume_drop(organisation_id=shop.organisation_id, window=W)

    assert c.type == 8
    assert c.chapter == "attention"
    assert c.headline == "\u221250%"
    assert c.title == "Fewer reviews at {store}"
    assert c.body == "{store} received 5 reviews in the last 30 days, down from 10."
    assert c.visual == {"kind": "before_now", "before": 10, "now": 5}
    assert c.link == {"store": shop.id, "from": "2026-10-15", "to": "2026-11-13"}
    assert c.review_count == 5


def test_volume_drop_not_above_half_or_below_ten_before():
    shop = ShopFactory()
    mk(shop, in_before(), n=10)
    mk(shop, in_now(), n=6)
    assert rules.volume_drop(organisation_id=shop.organisation_id, window=W) == []

    thin = ShopFactory()
    mk(thin, in_before(), n=9)
    assert rules.volume_drop(organisation_id=thin.organisation_id, window=W) == []


def test_volume_drop_counts_store_with_no_recent_reviews():
    shop = ShopFactory()
    mk(shop, in_before(), n=10)
    [c] = rules.volume_drop(organisation_id=shop.organisation_id, window=W)
    assert c.headline == "\u2212100%"
    assert c.review_count == 0


# --------------------------------------------------------------------------- scoping


def _s1(org) -> None:
    shop = ShopFactory(organisation=org)
    OrgCanonicalTagFactory(organisation=org, label=f"Wait time {shop.id}")
    tagged(shop, in_now(), f"wait time {shop.id}", n=5, sentiment="negative")


def _s2(org) -> None:
    mk(ShopFactory(organisation=org), in_now(), n=3, sentiment="negative")


def _s3(org) -> None:
    mk(ShopFactory(organisation=org), in_now(), n=10, star_rating=3)
    mk(ShopFactory(organisation=org), in_now(), n=10, star_rating=5)


def _s4(org) -> None:
    shop = ShopFactory(organisation=org)
    mk(shop, in_now(), n=10, star_rating=5)
    mk(shop, in_before(), n=10, star_rating=3)


def _s5(org) -> None:
    shop = ShopFactory(organisation=org)
    mk(shop, in_now(), n=20, is_replied=True)
    mk(shop, in_before(), n=20)


def _s6(org) -> None:
    _three_good_windows(ShopFactory(organisation=org), [5] * 10)


def _s7(org) -> None:
    shop = ShopFactory(organisation=org)
    OrgCanonicalTagFactory(organisation=org, label=f"Parking {shop.id}")
    tagged(shop, in_now(), f"parking {shop.id}", n=5)


def _s8(org) -> None:
    mk(ShopFactory(organisation=org), in_before(), n=10)


RuleFn = Callable[..., list[Candidate]]
SCENARIOS: list[tuple[RuleFn, Callable]] = [
    (rules.complaint_rising, _s1),
    (rules.waiting_negative, _s2),
    (rules.store_below_brand, _s3),
    (rules.five_star_share_change, _s4),
    (rules.reply_rate_change, _s5),
    (rules.best_month, _s6),
    (rules.new_tag, _s7),
    (rules.volume_drop, _s8),
]
IDS = [fn.__name__ for fn, _ in SCENARIOS]


@pytest.mark.parametrize(("rule", "build"), SCENARIOS, ids=IDS)
def test_inactive_shops_are_never_counted(rule, build):
    org = OrganisationFactory()
    build(org)
    assert rule(organisation_id=org.id, window=W)
    Shop.objects.filter(organisation=org).update(is_active=False)
    assert rule(organisation_id=org.id, window=W) == []


@pytest.mark.parametrize(("rule", "build"), SCENARIOS, ids=IDS)
def test_deleted_reviews_are_never_counted(rule, build):
    org = OrganisationFactory()
    build(org)
    assert rule(organisation_id=org.id, window=W)
    Review.objects.filter(organisation=org).update(deleted_at=timezone.now())
    assert rule(organisation_id=org.id, window=W) == []


@pytest.mark.parametrize(("rule", "build"), SCENARIOS, ids=IDS)
def test_other_organisations_are_never_counted(rule, build):
    mine = OrganisationFactory()
    theirs = OrganisationFactory()
    build(theirs)
    assert rule(organisation_id=theirs.id, window=W)
    assert rule(organisation_id=mine.id, window=W) == []


@pytest.mark.parametrize(("rule", "build"), SCENARIOS, ids=IDS)
def test_review_count_matches_reviews_page_link(rule, build):
    org = OrganisationFactory()
    build(org)
    found = rule(organisation_id=org.id, window=W)
    assert found
    for c in found:
        assert c.review_count == link_count(org.id, c.link), c


def test_window_edges_match_reviews_page_date_filter():
    """Reviews at the window's edge instants are counted exactly as the Reviews filter does."""
    shop = ShopFactory()
    mk(shop, in_before(), n=12)
    edges = [
        at(W.before_to, 23, 59, 59, 999999),
        at(W.now_from, 0),
        at(W.now_to, 0),
        at(W.now_to, 12),
        at(W.now_to, 23, 59, 59, 999999),
        at(TODAY, 0),
    ]
    for when in edges:
        mk(shop, when)
    [c] = rules.volume_drop(organisation_id=shop.organisation_id, window=W)
    assert c.review_count == link_count(shop.organisation_id, c.link)


# --------------------------------------------------------------------------- query counts


@pytest.mark.parametrize(("rule", "build"), SCENARIOS, ids=IDS)
def test_each_rule_runs_in_fixed_queries(rule, build):
    small = OrganisationFactory()
    big = OrganisationFactory()
    for _ in range(2):
        build(small)
    for _ in range(6):
        build(big)

    with CaptureQueriesContext(connection) as few:
        rule(organisation_id=small.id, window=W)
    with CaptureQueriesContext(connection) as many:
        found = rule(organisation_id=big.id, window=W)

    assert found
    assert len(few.captured_queries) == len(many.captured_queries)
    assert len(many.captured_queries) <= 4


def test_store_below_brand_headline_matches_rounded_body_values():
    org = OrganisationFactory()
    low = ShopFactory(organisation=org)
    high = ShopFactory(organisation=org)
    mk(low, in_now(), n=7, star_rating=4)
    mk(low, in_now(), n=3, star_rating=3)  # 3.7
    mk(high, in_now(), n=10, star_rating=5)  # brand 4.35 -> 4.4 (half up); true gap 0.65
    [c] = rules.store_below_brand(organisation_id=org.id, window=W)
    assert "averaged 3.7\u2605" in c.body
    assert "against 4.4\u2605" in c.body
    assert c.headline == "\u22120.7\u2605"  # 4.4 - 3.7, as the reader can verify from the body
