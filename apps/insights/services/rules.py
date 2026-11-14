"""Insight rules, types 1-8 (spec §2.4 / §2.7). DB-only, read-only, organisation-scoped.

Each rule returns ``Candidate`` objects. Text fields are templates: numbers are filled in,
``{store}`` / ``{tag}`` / ``{tag_lower}`` are resolved when the book is read. Every rule
counts only non-deleted reviews of the organisation's active shops, and bounds dates with
``review_window_q`` (the Reviews page's own date filter), so ``review_count`` equals what
``link`` shows on the Reviews page. Thresholds compare exact fractions, never floats.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any, Literal

from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Sum,
    Value,
    When,
)

from apps.insights.services.windows import Window, review_window_q, six_windows
from apps.reviews.models import OrgCanonicalTag, Review, ReviewTag

Chapter = Literal["attention", "good"]

MINUS = "\u2212"  # minus sign, for headlines such as "\u22120.7★"
TIMES = "\u00d7"  # multiplication sign, for ratio headlines such as "2.5\u00d7"
NEGATIVE = "negative"
SEE_REVIEWS = "See reviews"

# Type weights (spec §4): "waiting for a reply" (2) and "complaint rising" (1) lead.
WEIGHTS = {1: 1.4, 2: 1.5, 3: 1.2, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.1, 8: 1.0}

# Minimum samples and thresholds (spec §2.4).
T1_MIN_NOW = 5
T2_MIN = 3
T2_MAX_BARS = 10
T3_MIN_NOW = 10
T3_GAP = Fraction(1, 2)
T4_MIN_EACH = 10
T4_POINTS = 10
T5_MIN_EACH = 20
T5_POINTS = 10
T6_MIN_WINDOW = 10
T6_MIN_WINDOWS = 3
T7_MIN_NOW = 5
T8_MIN_BEFORE = 10


@dataclass(frozen=True)
class Candidate:
    type: int
    chapter: Chapter
    score: float
    headline: str
    title: str
    body: str
    visual: dict[str, Any]
    link: dict[str, Any]
    store_id: int | None
    tag_text: str | None
    review_count: int
    cta: str
    caption: str


# --------------------------------------------------------------------------- helpers


def mention_q(tag_text: str, *, review_ref: str = "pk") -> Exists:
    """Review mentions ``tag_text``: a ReviewTag whose own or canonical label iexact-matches it."""
    return Exists(
        ReviewTag.objects.filter(review=OuterRef(review_ref)).filter(
            Q(label__iexact=tag_text) | Q(canonical_tag__label__iexact=tag_text)
        )
    )


def _reviews(organisation_id: int) -> QuerySet[Review]:
    return Review.objects.filter(
        organisation_id=organisation_id, deleted_at__isnull=True, shop__is_active=True
    )


def _link(window: Window, **params: Any) -> dict[str, Any]:
    return {**params, "from": window.now_from.isoformat(), "to": window.now_to.isoformat()}


def _round(value: Fraction, places: int) -> Decimal:
    exp = Decimal(1).scaleb(-places)
    return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(exp, ROUND_HALF_UP)


def _pct(num: int, den: int) -> int:
    return int(_round(Fraction(100 * num, den), 0))


def _bucket_case(spans: list[tuple[dt.date, dt.date]], *, prefix: str = "") -> Case:
    return Case(
        *[
            When(review_window_q(f, t, prefix=prefix), then=Value(i))
            for i, (f, t) in enumerate(spans)
        ],
        default=Value(-1),
        output_field=IntegerField(),
    )


def _shop_windows(organisation_id: int, window: Window) -> list[dict[str, Any]]:
    """Per active shop, per 30-day window i (0 oldest .. 5 = now): n{i}, five{i}, stars{i}.

    One grouped query over the six-window span.
    """
    spans = six_windows(window)
    annotations: dict[str, Any] = {}
    for i, (f, t) in enumerate(spans):
        q = review_window_q(f, t)
        annotations[f"n{i}"] = Count("id", filter=q)
        annotations[f"five{i}"] = Count("id", filter=q & Q(star_rating=5))
        annotations[f"stars{i}"] = Sum("star_rating", filter=q)
    return list(
        _reviews(organisation_id)
        .filter(review_window_q(spans[0][0], spans[-1][1]))
        .values("shop_id")
        .annotate(**annotations)
        .order_by("shop_id")
    )


def _canonical_labels(organisation_id: int) -> dict[str, str]:
    """Upper-cased label -> canonical label, for the organisation's canonical tags."""
    labels = OrgCanonicalTag.objects.filter(organisation_id=organisation_id).values_list(
        "label", flat=True
    )
    return {label.upper(): label for label in labels}


def _tag_mentions(
    organisation_id: int,
    spans: list[tuple[dt.date, dt.date]],
    *,
    negative_only: bool = False,
) -> dict[str, dict[int, dict[int, dict[int, str]]]]:
    """canonical label -> bucket -> shop_id -> {review_id: sentiment} (distinct reviews).

    A ReviewTag row mentions a canonical tag when its own label or its canonical tag's
    label equals it, case-insensitively (same rule as ``mention_q``). One query for the
    canonical vocabulary, one for the tag rows.
    """
    canon = _canonical_labels(organisation_id)
    if not canon:
        return {}
    rows = ReviewTag.objects.filter(
        review__organisation_id=organisation_id,
        review__deleted_at__isnull=True,
        review__shop__is_active=True,
    ).filter(review_window_q(spans[0][0], spans[-1][1], prefix="review__"))
    if negative_only:
        rows = rows.filter(review__sentiment=NEGATIVE)
    tag_rows = rows.annotate(bucket=_bucket_case(spans, prefix="review__")).values_list(
        "review_id",
        "review__shop_id",
        "bucket",
        "review__sentiment",
        "label",
        "canonical_tag__label",
    )
    out: dict[str, dict[int, dict[int, dict[int, str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    for review_id, shop_id, bucket, sentiment, label, canonical_label in tag_rows:
        if bucket < 0:
            continue
        for raw in (label, canonical_label):
            tag = canon.get(raw.upper()) if raw else None
            if tag is not None:
                out[tag][bucket][shop_id][review_id] = sentiment
    return out


# --------------------------------------------------------------------------- type 1


def complaint_rising(*, organisation_id: int, window: Window) -> list[Candidate]:
    """Negative-sentiment reviews at a store mentioning a canonical tag: now >= 5, >= 2x before."""
    spans = [(window.before_from, window.before_to), (window.now_from, window.now_to)]
    mentions = _tag_mentions(organisation_id, spans, negative_only=True)
    out = []
    for tag in sorted(mentions):
        by_bucket = mentions[tag]
        for shop_id in sorted(by_bucket[1]):
            now = len(by_bucket[1][shop_id])
            before = len(by_bucket[0].get(shop_id, {}))
            if now < T1_MIN_NOW or now < 2 * before:
                continue
            if before:
                ratio = Fraction(now, before)
                headline = f"{_round(ratio, 1).normalize():f}{TIMES}"
                verb = "tripled" if ratio >= 3 else "doubled"
                title = f"{{tag}} complaints {verb} at {{store}}"
                body = (
                    f"{now} reviews mentioned {{tag_lower}} in the last 30 days, up from {before}."
                )
            else:
                ratio = Fraction(now, 1)
                headline = str(now)
                title = "New {tag} complaints at {store}"
                body = (
                    f"{now} reviews mentioned {{tag_lower}} in the last 30 days, "
                    "none in the 30 days before."
                )
            out.append(
                Candidate(
                    type=1,
                    chapter="attention",
                    score=WEIGHTS[1] * float(ratio) / 2,
                    headline=headline,
                    title=title,
                    body=body,
                    visual={"kind": "before_now", "before": before, "now": now},
                    link=_link(window, store=shop_id, tags=tag, sentiment=NEGATIVE),
                    store_id=shop_id,
                    tag_text=tag,
                    review_count=now,
                    cta=SEE_REVIEWS,
                    caption="Negative reviews mentioning {tag_lower} at {store}",
                )
            )
    return out


# --------------------------------------------------------------------------- type 2


def waiting_negative(*, organisation_id: int, window: Window) -> list[Candidate]:
    """>= 3 negative-sentiment, unreplied reviews in *now* (brand-wide)."""
    qs = _reviews(organisation_id).filter(
        review_window_q(window.now_from, window.now_to), sentiment=NEGATIVE, is_replied=False
    )
    count = qs.count()
    if count < T2_MIN:
        return []
    today = window.now_to + dt.timedelta(days=1)
    created = qs.order_by("review_create_time").values_list("review_create_time", flat=True)
    days = [(today - t.astimezone(dt.UTC).date()).days for t in created[:T2_MAX_BARS]]
    oldest = days[0]
    return [
        Candidate(
            type=2,
            chapter="attention",
            score=WEIGHTS[2] * (count / T2_MIN + oldest / 7),
            headline=str(count),
            title=f"{count} negative reviews are waiting for a reply",
            body=(
                f"{count} negative reviews from the last 30 days have no reply yet. "
                f"The oldest has waited {oldest} days."
            ),
            visual={"kind": "waiting_days", "days": days},
            link=_link(window, sentiment=NEGATIVE, replied="false"),
            store_id=None,
            tag_text=None,
            review_count=count,
            cta="Reply now",
            caption="Days each review has waited",
        )
    ]


# --------------------------------------------------------------------------- type 3


def store_below_brand(*, organisation_id: int, window: Window) -> list[Candidate]:
    """A store with >= 10 reviews *now* averaging >= 0.5 star below the brand average *now*."""
    rows = [r for r in _shop_windows(organisation_id, window) if r["n5"]]
    total_n = sum(r["n5"] for r in rows)
    if not total_n:
        return []
    brand = Fraction(sum(r["stars5"] for r in rows), total_n)
    out = []
    for r in rows:
        n = r["n5"]
        if n < T3_MIN_NOW:
            continue
        avg = Fraction(r["stars5"], n)
        gap = brand - avg
        if gap < T3_GAP:
            continue
        out.append(
            Candidate(
                type=3,
                chapter="attention",
                score=WEIGHTS[3] * float(gap / T3_GAP),
                headline=f"{MINUS}{_round(gap, 1)}★",
                title="{store} is rated below your brand",
                body=(
                    f"{{store}} averaged {_round(avg, 1)}★ from {n} reviews in the last 30 days, "
                    f"against {_round(brand, 1)}★ across all stores."
                ),
                visual={
                    "kind": "rating_line",
                    "store": float(_round(avg, 2)),
                    "brand": float(_round(brand, 2)),
                },
                link=_link(window, store=r["shop_id"]),
                store_id=r["shop_id"],
                tag_text=None,
                review_count=n,
                cta=SEE_REVIEWS,
                caption="{store} against the brand average, last 30 days",
            )
        )
    return out


# --------------------------------------------------------------------------- type 4


def five_star_share_change(*, organisation_id: int, window: Window) -> list[Candidate]:
    """A store with >= 10 reviews in both windows whose 5-star share moved >= 10 points."""
    out = []
    for r in _shop_windows(organisation_id, window):
        n_now, n_before = r["n5"], r["n4"]
        if n_now < T4_MIN_EACH or n_before < T4_MIN_EACH:
            continue
        share_now = Fraction(100 * r["five5"], n_now)
        share_before = Fraction(100 * r["five4"], n_before)
        diff = share_now - share_before
        if abs(diff) < T4_POINTS:
            continue
        up = diff > 0
        now_pct, before_pct = _pct(r["five5"], n_now), _pct(r["five4"], n_before)
        points = [
            float(_round(Fraction(100 * r[f"five{i}"], r[f"n{i}"]), 1)) if r[f"n{i}"] else None
            for i in range(6)
        ]
        out.append(
            Candidate(
                type=4,
                chapter="good" if up else "attention",
                score=WEIGHTS[4] * float(abs(diff) / T4_POINTS),
                headline=f"{now_pct}%",
                title=("More" if up else "Fewer") + " 5-star reviews at {store}",
                body=(
                    f"{now_pct}% of reviews were 5-star in the last 30 days, "
                    f"{'up' if up else 'down'} from {before_pct}%."
                ),
                visual={"kind": "share_line", "points": points},
                link=_link(window, store=r["shop_id"], rating=5),
                store_id=r["shop_id"],
                tag_text=None,
                review_count=r["five5"],
                cta=SEE_REVIEWS,
                caption="Share of 5-star reviews at {store}, last 6 months",
            )
        )
    return out


# --------------------------------------------------------------------------- type 5


def reply_rate_change(*, organisation_id: int, window: Window) -> list[Candidate]:
    """Brand reply rate moved >= 10 points, with >= 20 reviews in both windows."""
    now_q = review_window_q(window.now_from, window.now_to)
    before_q = review_window_q(window.before_from, window.before_to)
    agg = _reviews(organisation_id).aggregate(
        n_now=Count("id", filter=now_q),
        r_now=Count("id", filter=now_q & Q(is_replied=True)),
        n_before=Count("id", filter=before_q),
        r_before=Count("id", filter=before_q & Q(is_replied=True)),
    )
    n_now, r_now, n_before, r_before = (
        agg["n_now"],
        agg["r_now"],
        agg["n_before"],
        agg["r_before"],
    )
    if n_now < T5_MIN_EACH or n_before < T5_MIN_EACH:
        return []
    diff = Fraction(100 * r_now, n_now) - Fraction(100 * r_before, n_before)
    if abs(diff) < T5_POINTS:
        return []
    up = diff > 0
    now_pct, before_pct = _pct(r_now, n_now), _pct(r_before, n_before)
    link = _link(window) if up else _link(window, replied="false")
    return [
        Candidate(
            type=5,
            chapter="good" if up else "attention",
            score=WEIGHTS[5] * float(abs(diff) / T5_POINTS),
            headline=f"{now_pct}%",
            title=f"Your reply rate {'rose' if up else 'fell'} to {now_pct}%",
            body=(
                f"You replied to {r_now} of {n_now} reviews from the last 30 days, "
                f"{'up' if up else 'down'} from {before_pct}% in the 30 days before."
            ),
            visual={"kind": "progress", "before": before_pct, "now": now_pct},
            link=link,
            store_id=None,
            tag_text=None,
            review_count=n_now if up else n_now - r_now,
            cta="See replies" if up else SEE_REVIEWS,
            caption="Reviews replied to, last 30 days against the 30 days before",
        )
    ]


# --------------------------------------------------------------------------- type 6


def best_month(*, organisation_id: int, window: Window) -> list[Candidate]:
    """A store's *now* average beats every other 30-day window (>= 10 reviews) of 6 months.

    Needs >= 3 qualifying windows including *now*. A tie with an earlier window is not a best.
    """
    out = []
    for r in _shop_windows(organisation_id, window):
        n = r["n5"]
        if n < T6_MIN_WINDOW:
            continue
        avgs = [Fraction(r[f"stars{i}"], r[f"n{i}"]) if r[f"n{i}"] else None for i in range(6)]
        previous = [
            Fraction(r[f"stars{i}"], r[f"n{i}"]) for i in range(5) if r[f"n{i}"] >= T6_MIN_WINDOW
        ]
        if len(previous) + 1 < T6_MIN_WINDOWS:
            continue
        now_avg, prev_best = Fraction(r["stars5"], n), max(previous)
        if now_avg <= prev_best:
            continue
        out.append(
            Candidate(
                type=6,
                chapter="good",
                score=WEIGHTS[6] * float(now_avg / prev_best),
                headline=f"{_round(now_avg, 1)}★",
                title="{store} had its best month in six months",
                body=(
                    f"{{store}} averaged {_round(now_avg, 1)}★ from {n} reviews in the last "
                    f"30 days, its highest in six months (previous best {_round(prev_best, 1)}★)."
                ),
                visual={
                    "kind": "monthly_bars",
                    "points": [None if a is None else float(_round(a, 2)) for a in avgs],
                },
                link=_link(window, store=r["shop_id"]),
                store_id=r["shop_id"],
                tag_text=None,
                review_count=n,
                cta=SEE_REVIEWS,
                caption="Average rating at {store} per 30 days, last 6 months",
            )
        )
    return out


# --------------------------------------------------------------------------- type 7


def new_tag(*, organisation_id: int, window: Window) -> list[Candidate]:
    """A canonical tag with >= 5 mentions *now* and none in the five 30-day windows before."""
    mentions = _tag_mentions(organisation_id, six_windows(window))
    out = []
    for tag in sorted(mentions):
        by_bucket = mentions[tag]
        if any(by_bucket.get(i) for i in range(5)):
            continue
        reviews: dict[int, str] = {}
        for per_shop in by_bucket[5].values():
            reviews.update(per_shop)
        n = len(reviews)
        if n < T7_MIN_NOW:
            continue
        negative = sum(1 for s in reviews.values() if s == NEGATIVE)
        items = sorted(
            ({"store_id": sid, "count": len(rs)} for sid, rs in by_bucket[5].items()),
            key=lambda i: (-i["count"], i["store_id"]),
        )
        out.append(
            Candidate(
                type=7,
                chapter="attention" if 2 * negative > n else "good",
                score=WEIGHTS[7] * n / T7_MIN_NOW,
                headline=str(n),
                title="{tag} is a new topic in your reviews",
                body=(
                    f"{n} reviews mentioned {{tag_lower}} in the last 30 days, "
                    "and none in the five months before."
                ),
                visual={"kind": "store_bars", "items": items},
                link=_link(window, tags=tag),
                store_id=None,
                tag_text=tag,
                review_count=n,
                cta=SEE_REVIEWS,
                caption="Reviews mentioning {tag_lower} per store",
            )
        )
    return out


# --------------------------------------------------------------------------- type 8


def volume_drop(*, organisation_id: int, window: Window) -> list[Candidate]:
    """A store with >= 10 reviews *before* and *now* <= 50 % of *before*."""
    out = []
    for r in _shop_windows(organisation_id, window):
        now, before = r["n5"], r["n4"]
        if before < T8_MIN_BEFORE or 2 * now > before:
            continue
        drop = Fraction(before - now, before)
        out.append(
            Candidate(
                type=8,
                chapter="attention",
                score=WEIGHTS[8] * float(drop / Fraction(1, 2)),
                headline=f"{MINUS}{_pct(before - now, before)}%",
                title="Fewer reviews at {store}",
                body=f"{{store}} received {now} reviews in the last 30 days, down from {before}.",
                visual={"kind": "before_now", "before": before, "now": now},
                link=_link(window, store=r["shop_id"]),
                store_id=r["shop_id"],
                tag_text=None,
                review_count=now,
                cta=SEE_REVIEWS,
                caption="Reviews at {store}, last 30 days against the 30 days before",
            )
        )
    return out
