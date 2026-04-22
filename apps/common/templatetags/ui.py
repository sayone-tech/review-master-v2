from django import template
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
