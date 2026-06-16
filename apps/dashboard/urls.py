from django.urls import path

from apps.dashboard.views import (
    DashboardTagPolarityView,
    HighlightsView,
    KpisView,
    SentimentView,
    TopPerformingView,
    YourStoreView,
)

app_name = "dashboard"

urlpatterns = [
    path("kpis/", KpisView.as_view(), name="kpis"),
    path("sentiment-distribution/", SentimentView.as_view(), name="sentiment-distribution"),
    path("top-performing/", TopPerformingView.as_view(), name="top-performing"),
    path("highlights/", HighlightsView.as_view(), name="highlights"),
    path("your-store/", YourStoreView.as_view(), name="your-store"),
    path("tag-polarity/", DashboardTagPolarityView.as_view(), name="tag-polarity"),
]
