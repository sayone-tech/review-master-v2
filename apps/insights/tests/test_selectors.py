import pytest

from apps.insights.selectors import get_latest_insights
from apps.insights.tests.factories import InsightSnapshotFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import OrgCanonicalTag
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def _item(chapter="attention", store_id=None, tag_text=None, **kw):
    base = {
        "type": 1,
        "chapter": chapter,
        "score": 1.0,
        "headline": "5",
        "title": "{tag} complaints at {store}",
        "body": "Mentioned {tag_lower} at {store}.",
        "visual": {"kind": "before_now", "before": 1, "now": 5},
        "link": {"store": store_id, "tags": tag_text},
        "store_id": store_id,
        "tag_text": tag_text,
        "review_count": 5,
        "cta": "See reviews",
        "caption": "{store} / {tag_lower}",
    }
    return {**base, **kw}


def _canon(org, *labels):
    for label in labels:
        OrgCanonicalTag.objects.create(organisation=org, label=label)


def _snap(org, items):
    return InsightSnapshotFactory(
        organisation=org,
        payload={"cover": {"reviews": 40, "stores": 2, "attention": 9, "good": 9}, "items": items},
    )


def test_resolves_names_into_text():
    org = OrganisationFactory(name="Acme")
    shop = ShopFactory(organisation=org, name="Soho")
    _canon(org, "Slow Service")
    _snap(org, [_item(store_id=shop.id, tag_text="Slow Service")])
    book = get_latest_insights(organisation_id=org.id)
    item = book.items[0]
    assert item["title"] == "Slow Service complaints at Soho"
    assert item["body"] == "Mentioned slow service at Soho."
    assert item["caption"] == "Soho / slow service"
    assert item["store"] == "Soho"
    assert item["link"]["tags"] == "Slow Service"
    assert book.cover == {
        "organisation": "Acme",
        "reviews": 40,
        "stores": 2,
        "attention": 1,
        "good": 0,
    }


def test_org_wide_item_is_all_stores():
    org = OrganisationFactory()
    ShopFactory(organisation=org)
    _snap(org, [_item(chapter="good", title="Hello", body="b", caption="c")])
    item = get_latest_insights(organisation_id=org.id).items[0]
    assert item["store"] == "All stores"


def test_drops_deactivated_store_and_recomputes_cover():
    org = OrganisationFactory()
    keep = ShopFactory(organisation=org)
    gone = ShopFactory(organisation=org)
    _canon(org, "x", "Y", "Z")
    _snap(
        org,
        [
            _item(store_id=keep.id, tag_text="X"),
            _item(store_id=gone.id, tag_text="Y"),
            _item(chapter="good", store_id=gone.id, tag_text="Z"),
        ],
    )
    gone.is_active = False
    gone.save()
    book = get_latest_insights(organisation_id=org.id)
    assert len(book.items) == 1
    assert (book.cover["attention"], book.cover["good"]) == (1, 0)
    assert book.cover["reviews"] == 40


def test_all_items_stale_returns_none():
    org = OrganisationFactory()
    gone = ShopFactory(organisation=org, is_active=False)
    _snap(org, [_item(store_id=gone.id, tag_text="Y")])
    assert get_latest_insights(organisation_id=org.id) is None


def test_none_without_snapshot_and_other_org_never_returned():
    org, other = OrganisationFactory(), OrganisationFactory()
    shop = ShopFactory(organisation=other)
    _snap(other, [_item(store_id=shop.id, tag_text="X")])
    assert get_latest_insights(organisation_id=org.id) is None


def test_store_bars_maps_ids_to_names_and_drops_inactive():
    # Contract with the book: frontend/src/widgets/insights/InsightsBook.test.tsx store_bars
    # fixture uses exactly this output shape ({"store": <name>, "count"}).
    org = OrganisationFactory()
    a = ShopFactory(organisation=org, name="Kochi")
    b = ShopFactory(organisation=org, name="Calicut")
    gone = ShopFactory(organisation=org, name="Closed", is_active=False)
    _canon(org, "New Menu")
    visual = {
        "kind": "store_bars",
        "items": [
            {"store_id": a.id, "count": 4},
            {"store_id": gone.id, "count": 3},
            {"store_id": b.id, "count": 2},
        ],
    }
    _snap(org, [_item(chapter="good", tag_text="New Menu", visual=visual)])
    item = get_latest_insights(organisation_id=org.id).items[0]
    assert item["visual"] == {
        "kind": "store_bars",
        "items": [{"store": "Kochi", "count": 4}, {"store": "Calicut", "count": 2}],
    }


def test_drops_item_whose_tag_was_renamed():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    tag = OrgCanonicalTag.objects.create(organisation=org, label="Slow Service")
    _canon(org, "Cold Food")
    _snap(
        org,
        [
            _item(store_id=shop.id, tag_text="Slow Service"),
            _item(store_id=shop.id, tag_text="cold food"),  # case-insensitive match survives
            _item(chapter="good", title="Hello", body="b", caption="c"),
        ],
    )
    tag.label = "Waiting Time"
    tag.save()
    book = get_latest_insights(organisation_id=org.id)
    assert [i["type"] for i in book.items] == [1, 1]
    assert [i["chapter"] for i in book.items] == ["attention", "good"]
    assert (book.cover["attention"], book.cover["good"]) == (1, 1)
