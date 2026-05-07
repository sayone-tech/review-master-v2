"""Seed dummy stores + reviews for a given org.

Usage (from repo root):
    # Interactive (prompts for org id):
    python manage.py shell < scripts/seed_data/seed_org_reviews.py

    # Non-interactive (pass org id via env var):
    ORG_ID=2 python manage.py shell < scripts/seed_data/seed_org_reviews.py

The script creates:
  - 4 regions
  - 2 stores per region (8 stores total)
  - ~25 reviews per store (200 reviews total)
  All reviews have enrichment data (sentiment, tags) so the dashboard works immediately.

Safe to re-run: shops and regions use get_or_create; duplicate reviews are skipped.
"""

import os
import random
import uuid
from datetime import UTC, datetime, timedelta

from apps.organisations.models import Organisation
from apps.regions.models import Region
from apps.reviews.models import Review
from apps.shops.models import Shop

# ── Prompt ────────────────────────────────────────────────────────────────────

raw = os.environ.get("ORG_ID") or input("Enter Organisation ID: ").strip()
try:
    org_id = int(raw)
    org = Organisation.objects.get(pk=org_id)
except (ValueError, Organisation.DoesNotExist):
    print(f"Organisation with id '{raw}' not found. Aborting.")
    raise SystemExit(1)

allocated = org.number_of_stores
existing_count = Shop.objects.filter(organisation=org, is_active=True).count()
slots_remaining = allocated - existing_count

print(f"\nSeeding data for: {org.name} (id={org.pk})")
print(
    f"Store plan: {existing_count} existing / {allocated} allocated ({slots_remaining} slot(s) free)\n"
)

if slots_remaining <= 0:
    print(f"Organisation is already at its store limit ({allocated}). Nothing to create.")
    raise SystemExit(0)

# ── Config ────────────────────────────────────────────────────────────────────

REGIONS = [
    ("North Zone", "NZ"),
    ("South Zone", "SZ"),
    ("East Zone", "EZ"),
    ("West Zone", "WZ"),
]

# Candidate stores — the script fills up to `slots_remaining` from this pool in order
STORE_CANDIDATES = [
    ("Blossom Market", "12 Blossom Lane"),
    ("Green Corner", "88 Green Street"),
    ("Orchard Gate", "5 Orchard Road"),
    ("Sunrise Stall", "34 Sunrise Avenue"),
    ("Harvest Hub", "21 Harvest Drive"),
]

REVIEWS_PER_STORE = 25

REVIEWER_NAMES = [
    "Aisha Thomas",
    "Ben Carter",
    "Chloe Nair",
    "Daniel Wu",
    "Emily Rao",
    "Farrukh Aliev",
    "Gina Patel",
    "Harry Singh",
    "Irene Chow",
    "James Osei",
    "Kavya Menon",
    "Liam Brown",
    "Mia Fernandez",
    "Noah Kim",
    "Olivia Joshi",
    "Priya Sharma",
    "Quinn Ellis",
    "Riya Das",
    "Sam Okonkwo",
    "Tara Kapoor",
    "Umar Sheikh",
    "Vani Krishnan",
    "Will Zhang",
    "Xia Liu",
    "Yusuf Ibrahim",
]

POSITIVE_COMMENTS = [
    "Absolutely love this place! The mangoes are always ripe and sweet — I keep coming back every week.",
    "Freshest fruits I've found in the city. The staff are incredibly helpful and always smiling.",
    "Amazing selection of exotic fruits that you can't find elsewhere. The dragon fruit and passion fruit are to die for!",
    "Top-notch quality and very fair prices. My go-to fruit shop without a doubt.",
    "The seasonal offerings are fantastic. They had perfect lychees that were gone within the day — I got lucky!",
    "Beautifully presented produce, clean store, and knowledgeable staff. Five stars all the way.",
    "Great loyalty programme. I've been a regular customer for over a year and always feel appreciated.",
    "Loved the fresh-cut fruit cups — perfect for a quick healthy snack on the go.",
    "Wide variety and good availability even on weekends. Never leave disappointed.",
    "They even helped me pick out a fruit gift basket — turned out perfect. Will definitely return.",
    "The pineapples here are always sweet and never sour. Best in town!",
    "My kids love coming here for the strawberry samples. Staff are always patient and friendly.",
    "Highly recommend the smoothie add-ons. Fresh fruit made to order — absolutely delicious.",
]

NEUTRAL_COMMENTS = [
    "Decent range of fruits but the pricing can be a bit high for everyday staples like apples and oranges.",
    "Good shop overall. Parking can be tricky on busy days but the produce is usually worth it.",
    "Fairly standard selection. Nothing spectacular but reliable quality for the basics.",
    "Friendly staff but the checkout queue can get long during peak hours.",
    "Products are good quality. Wish there were more organic options on offer.",
    "Reasonable prices for premium fruits. The everyday staples are a bit pricey though.",
    "Nice place. Opened a second branch recently which has improved wait times at the original location.",
]

NEGATIVE_COMMENTS = [
    "Bought a bag of grapes that went off the very next day. Very disappointing for the price I paid.",
    "Waited 10 minutes to be served while staff were chatting in the back. Won't rush back.",
    "Some of the berries at the bottom of the punnet were crushed. Needs better quality checks.",
    "Overpriced compared to the market down the road, and the selection wasn't anything special.",
    "The watermelon I bought was underripe and tasteless. Staff weren't very helpful when I raised it.",
]

TAGS_POSITIVE = [
    [
        {"label": "freshness", "polarity": "positive"},
        {"label": "staff friendliness", "polarity": "positive"},
    ],
    [
        {"label": "product variety", "polarity": "positive"},
        {"label": "value for money", "polarity": "positive"},
    ],
    [
        {"label": "fruit quality", "polarity": "positive"},
        {"label": "store cleanliness", "polarity": "positive"},
    ],
    [{"label": "exotic selection", "polarity": "positive"}],
    [
        {"label": "presentation", "polarity": "positive"},
        {"label": "pricing", "polarity": "positive"},
    ],
]

TAGS_NEUTRAL = [
    [{"label": "pricing", "polarity": "neutral"}, {"label": "variety", "polarity": "neutral"}],
    [
        {"label": "wait time", "polarity": "negative"},
        {"label": "product quality", "polarity": "positive"},
    ],
    [{"label": "parking", "polarity": "negative"}, {"label": "freshness", "polarity": "positive"}],
]

TAGS_NEGATIVE = [
    [
        {"label": "product quality", "polarity": "negative"},
        {"label": "freshness", "polarity": "negative"},
    ],
    [{"label": "staff service", "polarity": "negative"}],
    [
        {"label": "value for money", "polarity": "negative"},
        {"label": "product quality", "polarity": "negative"},
    ],
]

REPLY_TEMPLATES = [
    "Thank you so much for your kind words! We're delighted you enjoyed your visit and hope to see you again soon. 🍉",
    "Thanks for the lovely feedback! Your support means the world to our team. See you next time!",
    "We really appreciate you taking the time to leave a review. Freshness and quality are our top priorities — glad we delivered!",
    "So happy to hear you loved our selection! We work hard to bring you the best seasonal produce. Thank you!",
    "Thank you for the glowing review! We're always here to help you find the perfect fruit. 🍓",
]

APOLOGY_TEMPLATES = [
    "We're truly sorry to hear about your experience. This is not the standard we hold ourselves to. Please reach out to us directly and we'll make it right.",
    "Thank you for the honest feedback. We apologise for falling short of your expectations and will address this with our team immediately.",
    "We're sorry to hear this. Quality and customer service are our core values, and we clearly missed the mark here. Please contact us so we can resolve this for you.",
]


def rand_datetime(days_back_min: int, days_back_max: int) -> datetime:
    days_back = random.randint(days_back_min, days_back_max)
    offset_hours = random.randint(8, 20)
    return datetime.now(UTC) - timedelta(days=days_back, hours=offset_hours)


def make_review_data(org: Organisation, shop: Shop, index: int) -> dict:  # type: ignore[type-arg]
    """Generate one review's field values."""
    # Weight: 60% positive, 20% neutral, 20% negative
    bucket = random.choices(["positive", "neutral", "negative"], weights=[60, 20, 20])[0]

    if bucket == "positive":
        rating = random.choices([5, 4], weights=[70, 30])[0]
        comment = random.choice(POSITIVE_COMMENTS)
        sentiment = "positive"
        tags = random.choice(TAGS_POSITIVE)
    elif bucket == "neutral":
        rating = random.choices([3, 4], weights=[60, 40])[0]
        comment = random.choice(NEUTRAL_COMMENTS)
        sentiment = "neutral"
        tags = random.choice(TAGS_NEUTRAL)
    else:
        rating = random.choices([1, 2], weights=[50, 50])[0]
        comment = random.choice(NEGATIVE_COMMENTS)
        sentiment = "negative"
        tags = random.choice(TAGS_NEGATIVE)

    reviewer = random.choice(REVIEWER_NAMES)
    created = rand_datetime(30, 730)

    # ~55% of reviews have been replied to
    is_replied = random.random() < 0.55
    reply_comment = ""
    reply_time = None
    if is_replied:
        template = APOLOGY_TEMPLATES if bucket == "negative" else REPLY_TEMPLATES
        reply_comment = random.choice(template)
        reply_time = created + timedelta(hours=random.randint(2, 72))

    return {
        "organisation": org,
        "shop": shop,
        "google_review_id": f"dummy-{shop.pk}-{index}-{uuid.uuid4().hex[:8]}",
        "star_rating": rating,
        "reviewer_display_name": reviewer,
        "reviewer_is_anonymous": False,
        "comment": comment,
        "review_create_time": created,
        "review_update_time": created,
        "is_replied": is_replied,
        "reply_comment": reply_comment,
        "reply_update_time": reply_time,
        "enrichment_status": Review.EnrichmentStatus.SUCCESS,
        "enrichment_version": 1,
        "sentiment": sentiment,
        "tags": tags,
        "extracted_action_items": [],
    }


# ── Build store plan — generate all candidate names, skip existing ─────────────

existing_names = set(
    Shop.objects.filter(organisation=org, is_active=True).values_list("name", flat=True)
)

# Generate enough candidates to cover the slots (cycle through regions x store names)
candidates_needed = slots_remaining
store_plan: list[tuple[tuple[str, str], tuple[str, str], str]] = []
i = 0
while len(store_plan) < candidates_needed:
    region = REGIONS[i % len(REGIONS)]
    candidate = STORE_CANDIDATES[i % len(STORE_CANDIDATES)]
    full_name = f"{org.name} — {candidate[0]} ({region[0]})"
    if full_name not in existing_names:
        store_plan.append((region, candidate, full_name))
        existing_names.add(full_name)  # prevent duplicates within plan
    i += 1
    if i > len(REGIONS) * len(STORE_CANDIDATES) * 10:
        print("Warning: ran out of unique store name combinations.")
        break

# ── Seed ──────────────────────────────────────────────────────────────────────

total_regions = total_shops = total_reviews = 0

for (region_name, region_id_code), (_store_suffix, address), full_name in store_plan:
    region_obj, r_created = Region.objects.get_or_create(
        organisation=org,
        name=region_name,
        defaults={"region_id": region_id_code},
    )
    if r_created:
        total_regions += 1
        print(f"  [+] Region: {region_name}")

    shop, shop_created = Shop.objects.get_or_create(
        organisation=org,
        name=full_name,
        defaults={
            "region": region_obj,
            "street_address": address,
            "is_active": True,
            "connection_method": Shop.ConnectionMethod.NOT_CONNECTED,
            "connection_status": Shop.ConnectionStatus.NOT_CONNECTED,
        },
    )
    if shop_created:
        total_shops += 1
        print(f"  [+] Store: {full_name}")

    # Create reviews (skip if shop already has enough)
    existing_reviews = Review.objects.filter(shop=shop).count()
    if existing_reviews >= REVIEWS_PER_STORE:
        print(f"      → {existing_reviews} reviews already present, skipping")
        continue

    reviews_to_create = [Review(**make_review_data(org, shop, i)) for i in range(REVIEWS_PER_STORE)]
    Review.objects.bulk_create(reviews_to_create, ignore_conflicts=True)
    total_reviews += len(reviews_to_create)
    print(f"      → Created {len(reviews_to_create)} reviews")

print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Seed complete for: {org.name}

  Regions created : {total_regions}
  Stores created  : {total_shops}
  Reviews created : {total_reviews}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
