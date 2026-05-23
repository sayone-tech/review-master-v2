from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditLogCursorPagination(CursorPagination):
    """Cursor pagination for the audit log endpoint (D-08).

    Tuple ordering ``("-created_at", "id")`` provides a tie-breaker so cursor
    stability holds even when multiple AuditLog rows share the same
    ``created_at`` timestamp (RESEARCH.md Pitfall 3).
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = ("-created_at", "id")
