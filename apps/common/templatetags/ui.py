from typing import Any

from django import template
from django.core.paginator import Paginator as DjangoPaginator
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def is_active_route(context: template.Context, prefix: str) -> bool:
    """Return True when the current request path starts with prefix.

    Used by sidebar nav items to apply the active state class bundle.
    """
    request = context.get("request")
    if request is None:
        return False
    path: str = request.path
    if prefix == "/":
        return path == "/"
    return path.startswith(prefix)


@register.simple_tag(takes_context=True)
def is_active_url(context: template.Context, url_name: str) -> bool:
    """Return True when the current request path matches a named URL."""
    request = context.get("request")
    if request is None:
        return False
    try:
        target = reverse(url_name)
    except NoReverseMatch:
        return False
    path: str = request.path
    return path == target


@register.filter
def elided_page_range(page_obj: Any) -> Any:
    """Return a windowed page range with '…' markers for large paginations.

    Shows up to 2 pages on each side of the current page and 1 page at each end.
    """
    return page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)


@register.filter
def is_page_ellipsis(value: Any) -> bool:
    """Return True when value is the paginator ellipsis marker (not a page number)."""
    return bool(value == DjangoPaginator.ELLIPSIS)
