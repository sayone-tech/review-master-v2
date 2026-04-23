from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_transactional_email(
    *,
    to: list[str],
    subject: str,
    template_base: str,
    context: dict[str, object],
    reply_to: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    """Render {template_base}.txt and {template_base}.html and send via Django email backend.

    - `to`: recipient list
    - `template_base`: e.g. 'emails/invitation' -> templates/emails/invitation.{txt,html}
    - `context`: rendered into both templates
    - `reply_to`: defaults to [settings.DEFAULT_REPLY_TO]
    - `tags`: when set and AWS_SES_CONFIGURATION_SET is configured, emits SES headers
    """
    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or [settings.DEFAULT_REPLY_TO],
    )
    msg.attach_alternative(html_body, "text/html")
    cfg_set = getattr(settings, "AWS_SES_CONFIGURATION_SET", None)
    if tags and cfg_set:
        msg.extra_headers["X-SES-MESSAGE-TAGS"] = ", ".join(f"category={t}" for t in tags)
        msg.extra_headers["X-SES-CONFIGURATION-SET"] = cfg_set
    msg.send(fail_silently=False)
