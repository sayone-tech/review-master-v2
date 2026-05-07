"""Phase 11 — Reply submission service.

Posts a reply to Google synchronously. Persists locally only on success.
Writes AuditLog entries for reply_posted (success) and reply_failed (failure).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.common.locks import distributed_lock
from apps.common.models import AuditLog
from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleReplyError,
    GoogleUnreachableError,
)
from apps.integrations.google.oauth import _refresh_access_token
from apps.integrations.google.reviews_client import delete_reply as google_delete_reply
from apps.integrations.google.reviews_client import post_reply
from apps.reviews.exceptions import ReplyConflictError, ReplyFailedError
from apps.reviews.models import Review
from apps.shops.models import Shop

logger = logging.getLogger(__name__)

LOCK_KEY_TMPL = "lock:reply:review:{review_id}"
LOCK_TIMEOUT_SECONDS = 30


def _audit_failure(*, review: Review, actor: Any, code: str, message: str) -> None:
    AuditLog.objects.create(
        organisation_id=review.organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="review",
        entity_id=str(review.pk),
        action="reply_failed",
        after_data={"error_code": code, "error_message": message},
    )


def submit_reply(*, review: Review, comment: str, actor: Any) -> Review:
    """Post reply to Google synchronously; persist local row only on success.

    Raises:
        ReplyConflictError: per-review lock held by another request
        ReplyFailedError(code=...): Google API failure or network error
    """
    lock_key = LOCK_KEY_TMPL.format(review_id=review.pk)
    with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
        if not acquired:
            raise ReplyConflictError("Another reply submission for this review is in progress.")

        shop = review.shop
        try:
            access_token = _refresh_access_token(shop.google_refresh_token or "")
        except GoogleAuthError as exc:
            if exc.reason == "invalid_grant":
                Shop.objects.filter(pk=shop.pk).update(
                    connection_status=Shop.ConnectionStatus.EXPIRED
                )
                _audit_failure(
                    review=review,
                    actor=actor,
                    code="invalid_grant",
                    message="Google connection expired.",
                )
                raise ReplyFailedError(
                    code="invalid_grant",
                    message="Google connection expired. Reconnect Google in Shops.",
                ) from exc
            _audit_failure(
                review=review,
                actor=actor,
                code="auth_error",
                message=str(exc),
            )
            raise ReplyFailedError(code="auth_error", message=str(exc)) from exc

        try:
            reply_data = post_reply(
                access_token=access_token,
                account_name=shop.google_account_name,
                location_name=shop.google_location_name,
                review_id=review.google_review_id,
                comment=comment,
            )
        except GoogleAuthError as exc:
            if exc.reason == "invalid_grant":
                Shop.objects.filter(pk=shop.pk).update(
                    connection_status=Shop.ConnectionStatus.EXPIRED
                )
            _audit_failure(
                review=review,
                actor=actor,
                code="invalid_grant" if exc.reason == "invalid_grant" else "auth_error",
                message=str(exc),
            )
            raise ReplyFailedError(
                code="invalid_grant" if exc.reason == "invalid_grant" else "auth_error",
                message=str(exc),
            ) from exc
        except GoogleReplyError as exc:
            _audit_failure(
                review=review,
                actor=actor,
                code="reply_rejected",
                message=f"{exc.status}: {exc.body[:200]}",
            )
            raise ReplyFailedError(
                code="reply_rejected",
                message="Google rejected the reply. Please review the content and try again.",
            ) from exc
        except GoogleUnreachableError as exc:
            _audit_failure(
                review=review,
                actor=actor,
                code="unreachable",
                message="Google API unreachable.",
            )
            raise ReplyFailedError(
                code="unreachable",
                message="Google API is temporarily unavailable. Please try again.",
            ) from exc

        # SUCCESS path — persist locally and audit.
        authenticated_actor = actor if getattr(actor, "is_authenticated", False) else None
        with transaction.atomic():
            review.reply_comment = comment
            review.reply_update_time = timezone.now()
            review.is_replied = True
            review.replied_by = authenticated_actor
            review.save(
                update_fields=[
                    "reply_comment",
                    "reply_update_time",
                    "is_replied",
                    "replied_by",
                    "updated_at",
                ]
            )
            AuditLog.objects.create(
                organisation_id=review.organisation_id,
                actor=authenticated_actor,
                entity_type="review",
                entity_id=str(review.pk),
                action="reply_posted",
                after_data={
                    "google_response_status": 200,
                    "reply_update_time": str(reply_data.get("updateTime", "")),
                },
            )
        return review


def remove_reply(*, review: Review, actor: Any) -> Review:
    """Delete reply from Google synchronously; clear local fields only on success.

    Raises:
        ReplyConflictError: per-review lock held by another request
        ReplyFailedError(code=...): Google API failure or network error
    """
    lock_key = LOCK_KEY_TMPL.format(review_id=review.pk)
    with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
        if not acquired:
            raise ReplyConflictError("Another reply operation for this review is in progress.")

        shop = review.shop
        try:
            access_token = _refresh_access_token(shop.google_refresh_token or "")
        except GoogleAuthError as exc:
            if exc.reason == "invalid_grant":
                Shop.objects.filter(pk=shop.pk).update(
                    connection_status=Shop.ConnectionStatus.EXPIRED
                )
                _audit_failure(
                    review=review,
                    actor=actor,
                    code="invalid_grant",
                    message="Google connection expired.",
                )
                raise ReplyFailedError(
                    code="invalid_grant",
                    message="Google connection expired. Reconnect Google in Shops.",
                ) from exc
            _audit_failure(review=review, actor=actor, code="auth_error", message=str(exc))
            raise ReplyFailedError(code="auth_error", message=str(exc)) from exc

        try:
            google_delete_reply(
                access_token=access_token,
                account_name=shop.google_account_name,
                location_name=shop.google_location_name,
                review_id=review.google_review_id,
            )
        except GoogleAuthError as exc:
            if exc.reason == "invalid_grant":
                Shop.objects.filter(pk=shop.pk).update(
                    connection_status=Shop.ConnectionStatus.EXPIRED
                )
            _audit_failure(
                review=review,
                actor=actor,
                code="invalid_grant" if exc.reason == "invalid_grant" else "auth_error",
                message=str(exc),
            )
            raise ReplyFailedError(
                code="invalid_grant" if exc.reason == "invalid_grant" else "auth_error",
                message=str(exc),
            ) from exc
        except GoogleReplyError as exc:
            _audit_failure(
                review=review,
                actor=actor,
                code="reply_rejected",
                message=f"{exc.status}: {exc.body[:200]}",
            )
            raise ReplyFailedError(
                code="reply_rejected",
                message="Google rejected the delete request. Please try again.",
            ) from exc
        except GoogleUnreachableError as exc:
            _audit_failure(
                review=review, actor=actor, code="unreachable", message="Google API unreachable."
            )
            raise ReplyFailedError(
                code="unreachable",
                message="Google API is temporarily unavailable. Please try again.",
            ) from exc

        # SUCCESS path — clear reply fields and audit.
        authenticated_actor = actor if getattr(actor, "is_authenticated", False) else None
        with transaction.atomic():
            review.reply_comment = ""
            review.reply_update_time = None
            review.is_replied = False
            review.replied_by = None
            review.save(
                update_fields=[
                    "reply_comment",
                    "reply_update_time",
                    "is_replied",
                    "replied_by",
                    "updated_at",
                ]
            )
            AuditLog.objects.create(
                organisation_id=review.organisation_id,
                actor=authenticated_actor,
                entity_type="review",
                entity_id=str(review.pk),
                action="reply_deleted",
                after_data={},
            )
        return review
