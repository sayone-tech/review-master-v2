from __future__ import annotations

import pytest
from django.conf import settings
from django.core import mail
from django.test import override_settings

from apps.common.services.email import send_transactional_email

pytestmark = pytest.mark.django_db


def test_sends_single_email_with_subject_and_recipient():
    send_transactional_email(
        to=["a@b.com"],
        subject="Hi",
        template_base="emails/_test",
        context={"name": "Alice"},
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.to == ["a@b.com"]
    assert m.subject == "Hi"
    assert m.from_email == settings.DEFAULT_FROM_EMAIL
    assert "Hello Alice" in m.body
    assert m.alternatives[0][1] == "text/html"
    assert "Hello Alice" in m.alternatives[0][0]


def test_plain_text_and_html_alternative_are_both_attached():
    send_transactional_email(
        to=["test@example.com"],
        subject="Test",
        template_base="emails/_test",
        context={"name": "Bob"},
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    # body is plain text
    assert "Hello Bob" in m.body
    # alternatives[0] is HTML
    assert len(m.alternatives) == 1
    html_body, mime_type = m.alternatives[0]
    assert mime_type == "text/html"
    assert "Hello Bob" in html_body


def test_reply_to_defaults_to_settings_default_reply_to():
    send_transactional_email(
        to=["recipient@example.com"],
        subject="Default reply-to",
        template_base="emails/_test",
        context={"name": "Carol"},
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.reply_to == [settings.DEFAULT_REPLY_TO]


def test_custom_reply_to_overrides_default():
    send_transactional_email(
        to=["recipient@example.com"],
        subject="Custom reply-to",
        template_base="emails/_test",
        context={"name": "Dave"},
        reply_to=["x@y.com"],
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.reply_to == ["x@y.com"]


@override_settings(AWS_SES_CONFIGURATION_SET="my-config-set")
def test_ses_headers_added_when_config_set_and_tags_provided():
    send_transactional_email(
        to=["recipient@example.com"],
        subject="SES headers",
        template_base="emails/_test",
        context={"name": "Eve"},
        tags=["invitation"],
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.extra_headers.get("X-SES-CONFIGURATION-SET") == "my-config-set"
    assert m.extra_headers.get("X-SES-MESSAGE-TAGS") == "category=invitation"


@override_settings(AWS_SES_CONFIGURATION_SET=None)
def test_no_ses_headers_when_config_set_is_unset():
    send_transactional_email(
        to=["recipient@example.com"],
        subject="No SES headers",
        template_base="emails/_test",
        context={"name": "Frank"},
        tags=["invitation"],
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert "X-SES-CONFIGURATION-SET" not in m.extra_headers
    assert "X-SES-MESSAGE-TAGS" not in m.extra_headers
