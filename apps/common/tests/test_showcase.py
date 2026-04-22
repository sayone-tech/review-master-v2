import pytest


@pytest.mark.django_db
def test_showcase_page_returns_200(client):
    resp = client.get("/__ui__/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_showcase_page_includes_every_component(client):
    resp = client.get("/__ui__/")
    html = resp.content.decode()
    # Django partials
    assert 'data-testid="btn-primary"' in html
    assert 'data-testid="btn-danger"' in html
    assert 'data-testid="field-org_name"' in html
    assert 'data-testid="badge-green"' in html
    assert 'data-testid="empty-state"' in html
    assert 'data-testid="skeleton"' in html
    assert 'data-testid="filter-bar"' in html
    assert 'data-testid="pagination"' in html
    assert 'data-testid="toast-stack"' in html
    # React mount
    assert 'id="showcase-root"' in html
    assert 'data-testid="showcase-react-mount"' in html


@pytest.mark.django_db
def test_showcase_h1_and_h2_heading_hierarchy(client):
    resp = client.get("/__ui__/")
    html = resp.content.decode()
    assert '<h1 class="text-[26px]' in html
    assert (
        html.count("<h2 ") >= 7
    )  # Buttons, Form fields, Badges, Empty, Skeletons, Filter, Pagination, React
