# Insights (Org Admin "book")

The Insights page (`/admin/org/insights/`) and the Dashboard Spotlight strip read a daily snapshot per
organisation. Nothing is computed when the page loads.

| Item | Value |
|------|-------|
| Task | `apps.insights.tasks.compute_daily_insights_task` |
| Schedule | Celery Beat, daily 02:00 UTC (07:30 IST), `default` queue, periodic task `insights_compute_daily` |
| Writes | One `InsightSnapshot` row per organisation per day (re-running the same day replaces it); 14-day retention |
| Cost | Database only. **No OpenAI calls, no credits, no `AiUsageLog` rows.** |
| Window | The 30 full UTC days ending yesterday vs the 30 days before |

## Page shows "Not enough new reviews yet to spot changes"

That message means the organisation has no snapshot, or its latest snapshot has no insights.

1. **Just deployed?** The first snapshot appears after the next 02:00 UTC run. To fill it now, see below.
2. **Check the schedule and snapshots** (read-only, after the [standard session setup](README.md)):

   ```bash
   docker compose -f /opt/review-master/docker-compose.prod.yml exec -T web python manage.py shell -c "
   from django_celery_beat.models import PeriodicTask
   from apps.insights.models import InsightSnapshot
   print(PeriodicTask.objects.filter(task__icontains='insights').values('name','enabled','last_run_at'))
   for s in InsightSnapshot.objects.order_by('-computed_for')[:10]:
       print(s.organisation_id, s.computed_for, s.payload.get('cover'), len(s.payload.get('items', [])))
   "
   ```

   - No periodic task, or `last_run_at` empty for days: check that Beat is running and the insights migrations are
     applied (`showmigrations insights`).
   - A snapshot exists with 0 items: correct behaviour. No insight met its minimum sample (e.g. a store needs 10+
     reviews in the last 30 days for most insight types).

## Compute insights now (instead of waiting for 02:00 UTC)

Safe to run at any time and more than once (writes today's snapshot for every organisation, replacing it if present):

```bash
docker compose -f /opt/review-master/docker-compose.prod.yml exec -T web python manage.py shell -c "
from apps.insights.services.build import compute_all_insights
compute_all_insights()
"
```

One organisation failing does not stop the others; the run raises at the end listing the failed organisation ids.
