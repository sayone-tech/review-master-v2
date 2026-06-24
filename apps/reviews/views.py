"""Phase 11 — ReviewViewSet + review_list template view.

Phase 25 Plan 02 — OrgCanonicalTagViewSet, TagMergeJobViewSet, tags_page_view.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Exists, OuterRef, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import mixins, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.pagination import DefaultPageNumberPagination
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.integrations.openai.exceptions import (
    ContentModeratedException,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.reviews.exceptions import ReplyConflictError, ReplyFailedError
from apps.reviews.filters import ReviewFilterSet
from apps.reviews.models import OrgCanonicalTag, Review, TagMergeJob
from apps.reviews.selectors.canonical_tags import list_canonical_tags_for_org
from apps.reviews.selectors.reviews import (
    base_reviews_queryset,
    get_accessible_shop_ids,
)
from apps.reviews.serializers import (
    GenerateReplySerializer,
    OrgCanonicalTagReadSerializer,
    RenameSerializer,
    ReviewReadSerializer,
    ReviewReplySerializer,
    TagMergeJobSerializer,
)
from apps.reviews.services.replies import remove_reply, submit_reply
from apps.reviews.services.reply_generation import generate_reply_draft
from apps.reviews.services.tag_management import create_merge_job, rename_canonical_tag

logger = logging.getLogger(__name__)


class ReviewPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"


class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = ReviewReadSerializer
    pagination_class = ReviewPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]  # noqa: RUF012
    filterset_class = ReviewFilterSet
    ordering_fields = ["review_create_time", "star_rating"]  # noqa: RUF012
    ordering = ["-review_create_time"]  # noqa: RUF012
    throttle_scope = "review_reply"  # used only when ScopedRateThrottle is selected
    queryset = Review.objects.none()

    def get_throttles(self):  # type: ignore[no-untyped-def]
        """Set per-action throttle_scope BEFORE DRF instantiates throttles.

        WR-02: assigning ``self.throttle_scope`` inside the action body runs
        AFTER ``initial()`` has already evaluated the throttle against the
        class-level scope. Setting it here — invoked from ``initial()`` —
        ensures the correct rate is applied (10/min for generate_reply,
        30/min for reply).
        """
        if self.action == "generate_reply":
            self.throttle_scope = "generate_reply"
        elif self.action == "reply":
            self.throttle_scope = "review_reply"
        return super().get_throttles()

    def get_queryset(self) -> QuerySet[Review]:
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return Review.objects.none()
        # Phase 19 Plan 02: select_related("shop__organisation") so that the
        # generate_reply action can access review.shop.organisation.name in
        # generate_reply_draft() without an extra query (CLAUDE.md §6 N+1 guard).
        qs = base_reviews_queryset(organisation_id=org_id).select_related("shop__organisation")
        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            raw_pk = user.pk
            if raw_pk is None:
                return Review.objects.none()
            user_id: int = raw_pk
            qs = qs.filter(shop_id__in=get_accessible_shop_ids(user_id=user_id))
        # Phase 13 Plan 07 (B3): annotate has_action_items via Exists() so the
        # ReviewReadSerializer's BooleanField is folded into the existing list
        # JOIN — no extra queries (REVW-14 <=5 query budget preserved).
        # Local import to avoid app-load cycles between reviews and action_items.
        from apps.action_items.models import ActionItem

        return qs.annotate(
            has_action_items=Exists(ActionItem.objects.filter(source_review=OuterRef("pk")))
        )

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        total_count = qs.values("pk").count()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
        else:
            response = Response({"results": serializer.data})
        response.data["total_count"] = total_count
        return response

    @action(detail=False, methods=["get"], url_path="tags")
    def tags(self, request: Request) -> Response:
        """Return distinct tag labels + counts scoped to the caller's org.

        ?shop=<id> — optional, narrows to a single shop.
        Staff users see only tags from their accessible shops.
        """
        user = request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return Response([])

        # Local import — avoids any circular import risk at module load time.
        from apps.reviews.models import ReviewTag

        qs = ReviewTag.objects.filter(review__shop__organisation_id=org_id)

        # Phase 17 WR-02: validate ?shop as int. Without this, a non-numeric
        # value (e.g. ?shop=abc) propagates to the ORM and raises ValueError
        # at query time → 500. Mirrors the django-filter NumberFilter contract
        # on the list endpoint.
        shop_id_raw = request.query_params.get("shop")
        if shop_id_raw:
            try:
                shop_id = int(shop_id_raw)
            except (TypeError, ValueError):
                return Response({"detail": "Invalid shop id"}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(review__shop_id=shop_id)

        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            raw_pk = user.pk
            if raw_pk is None:
                return Response([])
            user_id: int = raw_pk
            qs = qs.filter(review__shop_id__in=get_accessible_shop_ids(user_id=user_id))

        # Phase 17 WR-03: hard-cap the response. Long-tail tag management UI
        # is the long-term solution; for now we bound the payload at top-N
        # by count (default 200) with a `?limit=` override. This matches the
        # discovery-style contract of /reviews/tags/ — a UI combobox source —
        # rather than the paginated list contract used for the reviews list.
        try:
            limit = int(request.query_params.get("limit", 200))
        except (TypeError, ValueError):
            limit = 200
        limit = max(1, min(limit, 500))

        result = qs.values("label").annotate(count=Count("id")).order_by("-count", "label")[:limit]
        return Response(
            [{"label": row["label"], "count": row["count"]} for row in result]  # type: ignore[index, unused-ignore]
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request: Request) -> Response:
        """Aggregate stats for the reviews list header cards."""
        qs = self.filter_queryset(self.get_queryset())
        agg = qs.aggregate(
            total=Count("pk"),
            avg_rating=Avg("star_rating"),
            awaiting_reply=Count("pk", filter=Q(is_replied=False)),
            positive_count=Count(
                "pk",
                filter=Q(sentiment="positive", enrichment_status=Review.EnrichmentStatus.SUCCESS),
            ),
            enriched_count=Count("pk", filter=Q(enrichment_status=Review.EnrichmentStatus.SUCCESS)),
        )
        total: int = agg["total"] or 0
        avg_rating: float = round(float(agg["avg_rating"] or 0.0), 1)
        awaiting_reply: int = agg["awaiting_reply"] or 0
        enriched: int = agg["enriched_count"] or 0
        positive_pct: int = (
            round((agg["positive_count"] or 0) / enriched * 100) if enriched > 0 else 0
        )
        return Response(
            {
                "total_count": total,
                "avg_rating": avg_rating,
                "awaiting_reply_count": awaiting_reply,
                "positive_sentiment_pct": positive_pct,
            }
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="reply",
        throttle_classes=[ScopedRateThrottle],
    )
    def reply(self, request: Request, pk: int | None = None) -> Response:
        """POST: submit reply to Google. DELETE: remove reply from Google."""
        self.throttle_scope = "review_reply"
        review = self.get_object()

        if request.method == "DELETE":
            if not review.is_replied:
                return Response(
                    {"detail": "This review has no reply to delete.", "code": "no_reply"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                updated = remove_reply(review=review, actor=request.user)
            except ReplyConflictError as exc:
                return Response(
                    {"detail": str(exc), "code": "conflict"},
                    status=status.HTTP_409_CONFLICT,
                )
            except ReplyFailedError as exc:
                return Response(
                    {"detail": exc.message, "code": exc.code},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response(ReviewReadSerializer(updated).data, status=status.HTTP_200_OK)

        serializer = ReviewReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = submit_reply(
                review=review,
                comment=serializer.validated_data["comment"],
                actor=request.user,
            )
        except ReplyConflictError as exc:
            return Response(
                {"detail": str(exc), "code": "conflict"},
                status=status.HTTP_409_CONFLICT,
            )
        except ReplyFailedError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(ReviewReadSerializer(updated).data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="reviews_generate_reply",
        summary="Generate an AI draft reply",
        description=(
            "Generates a tone-selected draft reply for the review using GPT-4o-mini. "
            "The draft is NOT sent to Google — it fills the composer textarea for the "
            "user to edit and submit. Input + output are passed through the OpenAI "
            "Moderation API (Phase 20 — D-23 category-aware blocking). Throttled at "
            "10/min/user (scope `generate_reply`)."
        ),
        request=GenerateReplySerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="GenerateReplyResponse",
                    fields={"draft": drf_serializers.CharField()},
                ),
                description="Draft generated successfully. Length capped at 300 words by D-08.",
                examples=[
                    OpenApiExample(
                        "Professional draft",
                        value={
                            "draft": (
                                "Thank you for taking the time to share your feedback. "
                                "We're sorry to hear about your experience and would "
                                "appreciate the opportunity to make this right..."
                            )
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid tone (not in `professional`/`friendly`)."),
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="Review is outside the caller's accessible shops."),
            422: OpenApiResponse(
                response=inline_serializer(
                    name="ContentModeratedResponse",
                    fields={
                        "code": drf_serializers.CharField(),
                        "detail": drf_serializers.CharField(),
                    },
                ),
                description=(
                    "Review text or generated draft was flagged by Moderation API "
                    "high-severity categories (Phase 20 D-23). Same canonical body "
                    "for both input and output flags (D-26) — frontend renders "
                    "`detail` verbatim."
                ),
                examples=[
                    OpenApiExample(
                        "Moderated content",
                        value={
                            "code": "content_moderated",
                            "detail": (
                                "AI reply isn't available for this review. "
                                "Please write your reply manually."
                            ),
                        },
                    )
                ],
            ),
            429: OpenApiResponse(
                response=inline_serializer(
                    name="GenerateReplyThrottledResponse",
                    fields={
                        "detail": drf_serializers.CharField(),
                        "retry_after_seconds": drf_serializers.IntegerField(required=False),
                    },
                ),
                description=(
                    "Rate limit exceeded (10/min/user). `retry_after_seconds` is the "
                    "integer seconds until the bucket refills. Frontend uses the dynamic "
                    "copy variant when present (see 19-UI-SPEC.md §Copywriting)."
                ),
            ),
            502: OpenApiResponse(
                response=inline_serializer(
                    name="GenerateReplyFailedResponse",
                    fields={
                        "code": drf_serializers.CharField(),
                        "detail": drf_serializers.CharField(),
                    },
                ),
                description=(
                    "OpenAI call failed (transient 5xx, permanent 4xx, or unexpected "
                    "error). A FAILED AiUsageLog row is always written before the "
                    "response is returned (D-17)."
                ),
                examples=[
                    OpenApiExample(
                        "OpenAI unavailable",
                        value={
                            "code": "ai_unavailable",
                            "detail": (
                                "AI generation failed. Please try again or "
                                "write your reply manually."
                            ),
                        },
                    )
                ],
            ),
        },
        tags=["reviews"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="generate-reply",
        throttle_classes=[ScopedRateThrottle],
    )
    def generate_reply(self, request: Request, pk: int | None = None) -> Response:
        """POST: generate an AI draft reply for the given review.

        Returns 200 {draft: str} on success.
        Returns 400 on invalid tone (serializer validation).
        Returns 502 on any OpenAI failure (transient/permanent/unexpected).
        D-09, D-10, D-11, D-12, D-13, D-17, D-18.

        Throttle scope is set in ``get_throttles`` (see WR-02) so DRF picks
        up the per-action rate BEFORE the action body executes.
        """
        review = self.get_object()
        serializer = GenerateReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tone: str = serializer.validated_data["tone"]
        try:
            draft = generate_reply_draft(review=review, tone=tone)
        except ContentModeratedException:
            # D-16/D-26/D-32: input or output blocked by moderation.
            # Caught BEFORE OpenAITransient/Permanent because
            # ContentModeratedException inherits from OpenAIError —
            # most-specific catch first. Body is the canonical user-facing
            # string from D-26; no LLM categories or review text leak (T-20-LK).
            logger.info(
                "generate_reply blocked by moderation review_id=%s",
                review.pk,
            )
            return Response(
                {
                    "code": "content_moderated",
                    "detail": "AI reply isn't available for this review. Please write your reply manually.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except (OpenAITransientError, OpenAIPermanentError) as exc:
            # D-17: known OpenAI failures (transient + permanent) map to a
            # single generic 502 response. Service layer has already written
            # the FAILED AiUsageLog row before re-raising.
            logger.warning(
                "generate_reply_openai_failed review_id=%s tone=%s exc_type=%s exc=%s",
                review.pk,
                tone,
                type(exc).__name__,
                exc,
            )
            return Response(
                {
                    "code": "ai_unavailable",
                    "detail": (
                        "AI generation failed. Please try again or write your reply manually."
                    ),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except APIException:
            # Let DRF handle Throttled, ValidationError, NotAuthenticated, etc.
            # with their natural status codes (e.g., 429, 400, 401).
            raise
        except Exception:
            # Unexpected programmer/runtime error — logger.exception emits
            # ERROR-level + traceback so Sentry captures it (D-17).
            logger.exception(
                "generate_reply_unexpected review_id=%s tone=%s",
                review.pk,
                tone,
            )
            return Response(
                {
                    "code": "ai_unavailable",
                    "detail": (
                        "AI generation failed. Please try again or write your reply manually."
                    ),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"draft": draft}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Phase 25 Plan 02 — OrgCanonicalTagViewSet (TMGT-01, TMGT-02, TMGT-03, TMGT-04)
# ---------------------------------------------------------------------------


class OrgCanonicalTagViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):  # type: ignore[type-arg]
    """Paginated, sortable canonical tag list + rename/merge actions.

    Permission: IsOrgAdmin only — Staff users get 403 (D-01).
    Sorting: OrderingFilter on label, review_count, created_at (§8).
    Query ceiling: 1 COUNT + 1 SELECT = ≤2 queries per paginated response (§6.9).
    """

    permission_classes = [IsOrgAdmin]  # noqa: RUF012 — Staff excluded (D-01, T-25-AC1)
    serializer_class = OrgCanonicalTagReadSerializer
    pagination_class = DefaultPageNumberPagination
    filter_backends = [OrderingFilter]  # noqa: RUF012
    ordering_fields = ["label", "review_count", "created_at"]  # noqa: RUF012
    ordering = ["-review_count"]  # noqa: RUF012
    queryset = OrgCanonicalTag.objects.none()  # required for router introspection

    def get_queryset(self) -> QuerySet[OrgCanonicalTag]:
        org_id = getattr(self.request.user, "organisation_id", None)
        if org_id is None:
            return OrgCanonicalTag.objects.none()
        return list_canonical_tags_for_org(
            organisation_id=org_id,
            search=self.request.query_params.get("search", ""),
        )

    @action(detail=True, methods=["patch"], url_path="rename")
    def rename(self, request: Request, pk: int | None = None) -> Response:
        """PATCH /canonical-tags/{id}/rename/ — O(1) label update (D-03/D-04).

        Returns the updated tag using the read serializer.
        ValidationError from the service (dup/length) → DRF 400.
        """
        tag = self.get_object()
        serializer = RenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # IsOrgAdmin permission ensures request.user is an authenticated User with organisation_id.
        org_id: int = request.user.organisation_id  # type: ignore[union-attr,assignment]
        try:
            updated = rename_canonical_tag(
                tag=tag,
                new_label=str(serializer.validated_data["label"]),
                organisation_id=org_id,
            )
        except DjangoValidationError as exc:
            # Convert Django ValidationError → DRF 400 response
            raise drf_serializers.ValidationError(exc.message_dict) from exc
        return Response(OrgCanonicalTagReadSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="merge")
    def merge(self, request: Request, pk: int | None = None) -> Response:
        """POST /canonical-tags/{id}/merge/ — enqueue a merge job (D-05/D-06/D-07).

        Returns {"job_id": <id>} with 201 Created.
        Returns 409 when an active merge job already exists for this org (T-25-AC3).
        Returns 404 when target_id doesn't belong to the caller's org (T-25-AC1b).
        """
        source = self.get_object()
        raw_target_id = request.data.get("target_id")
        if raw_target_id is None:
            raise drf_serializers.ValidationError({"target_id": "This field is required."})
        try:
            target_id = int(raw_target_id)
        except (TypeError, ValueError) as exc:
            raise drf_serializers.ValidationError({"target_id": "Must be an integer."}) from exc
        # IsOrgAdmin permission ensures request.user is an authenticated User with organisation_id.
        org_id: int = request.user.organisation_id  # type: ignore[union-attr,assignment]
        try:
            job = create_merge_job(
                source_tag=source,
                target_id=target_id,
                organisation_id=org_id,
            )
        except OrgCanonicalTag.DoesNotExist:
            return Response(
                {"detail": "Target tag not found in your organisation."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            # Active-job conflict: map the specific error to 409 (T-25-AC3)
            if "non_field_errors" in exc.message_dict:
                return Response(
                    {"detail": exc.message_dict["non_field_errors"][0]},
                    status=status.HTTP_409_CONFLICT,
                )
            raise drf_serializers.ValidationError(exc.message_dict) from exc
        return Response({"job_id": job.pk}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Phase 25 Plan 02 — TagMergeJobViewSet (TMGT-06)
# ---------------------------------------------------------------------------


class TagMergeJobViewSet(viewsets.GenericViewSet):  # type: ignore[type-arg]
    """Merge job poll and dismiss endpoints.

    Permission: IsOrgAdmin only — Staff users get 403 (D-01).
    get_queryset() scopes to caller's org so cross-org get_object() → 404 (T-25-AC1b).
    """

    permission_classes = [IsOrgAdmin]  # noqa: RUF012 — Staff excluded (D-01)
    serializer_class = TagMergeJobSerializer
    queryset = TagMergeJob.objects.none()  # required for router introspection

    def get_queryset(self) -> QuerySet[TagMergeJob]:
        org_id = getattr(self.request.user, "organisation_id", None)
        if org_id is None:
            return TagMergeJob.objects.none()
        return TagMergeJob.objects.filter(organisation_id=org_id)

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request: Request) -> Response:
        """GET /tag-merge-jobs/active/ — return the most-recent non-dismissed active job.

        Returns the serialized job or null when no active job exists.
        Scoped to caller's org — another org's jobs are never returned (T-25-AC1b).
        """
        org_id = getattr(request.user, "organisation_id", None)
        if org_id is None:
            return Response(None)
        job = (
            self.get_queryset()
            .filter(
                status__in=[TagMergeJob.Status.PENDING, TagMergeJob.Status.IN_PROGRESS],
                dismissed=False,
            )
            .order_by("-created_at")
            .first()
        )
        if job is None:
            return Response(None)
        return Response(TagMergeJobSerializer(job).data)

    @action(detail=True, methods=["patch"], url_path="dismiss")
    def dismiss(self, request: Request, pk: int | None = None) -> Response:
        """PATCH /tag-merge-jobs/{id}/dismiss/ — mark the job as dismissed.

        The job must belong to the caller's org (enforced by get_queryset scoping —
        cross-org get_object() returns 404, T-25-AC1b).
        """
        job = self.get_object()
        job.dismissed = True
        job.save(update_fields=["dismissed", "updated_at"])
        return Response(TagMergeJobSerializer(job).data)


# ---------------------------------------------------------------------------
# Phase 25 Plan 02 — Tags page template view (TMGT-01)
# ---------------------------------------------------------------------------


@org_admin_required  # NOT @login_required — Staff must be redirected, not admitted (D-01)
def tags_page_view(request: HttpRequest) -> HttpResponse:
    """Tags management page. ORG_ADMIN only — Staff redirected by @org_admin_required.

    Renders the Django template that mounts the #tag-management-root React widget.
    No bootstrap data needed — all data is fetched via the /api/v1/reviews/ DRF endpoints.
    """
    return render(request, "org-admin/tags.html", {})


@login_required(login_url="/login/")
def review_list(request):  # type: ignore[no-untyped-def]
    user = request.user
    open_progress = request.GET.get("open_progress") or ""
    org_id = getattr(user, "organisation_id", None)

    shops_data: list[Any] = []
    has_connected = False
    if org_id is not None:
        from apps.shops.models import Shop

        qs = Shop.objects.filter(organisation_id=org_id, is_active=True)
        if getattr(user, "role", "") == "STAFF_ADMIN":
            qs = qs.filter(id__in=get_accessible_shop_ids(user_id=user.pk))
        shops_data = list(qs.values("id", "name").order_by("name"))
        has_connected = qs.filter(connection_status=Shop.ConnectionStatus.CONNECTED).exists()

    return render(
        request,
        "reviews/review_list.html",
        {
            "page_title": "Reviews",
            "open_progress_shop_id": open_progress,
            "current_user_role": getattr(user, "role", ""),
            "shops_json": shops_data,
            "has_connected_shops": has_connected,
        },
    )
