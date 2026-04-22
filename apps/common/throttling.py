from rest_framework.throttling import ScopedRateThrottle


class InviteScopedThrottle(ScopedRateThrottle):
    scope = "invite"


class GoogleSyncScopedThrottle(ScopedRateThrottle):
    scope = "google_sync"
