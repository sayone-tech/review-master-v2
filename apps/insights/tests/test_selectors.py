import pytest

from apps.insights.selectors import get_latest_insights
from apps.insights.tests.factories import InsightSnapshotFactory
from apps.organisations.tests.factories import OrganisationFactory
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


def _snap(org, items):
    return InsightSnapshotFactory(
        organisation=org,
        payload={"cover": {"reviews": 40, "stores": 2, "attention": 9, "good": 9}, "items": items},
    )


def test_resolves_names_into_text():
    org = OrganisationFactory(name="Acme")
    shop = ShopFactory(organisation=org, name="Soho")
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
