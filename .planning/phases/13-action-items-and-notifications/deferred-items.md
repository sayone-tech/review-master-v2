## Out-of-Scope Discovery (during 13-01 execution)

- `apps/notifications/models.py` exists but has no migration. `manage.py makemigrations --check` reports a missing migration for the Notification model. This is out of scope for plan 13-01 (which owns only ActionItem). The notifications app migration belongs to a later Phase 13 plan (likely 13-05 or the notifications-focused plan). No action taken.
