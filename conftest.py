import django
from django.conf import settings  # noqa: F401


def pytest_configure(config: object) -> None:  # type: ignore[no-untyped-def]
    django.setup()
