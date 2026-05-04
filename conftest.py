import django
from django.conf import settings  # noqa: F401


def pytest_configure(config: object) -> None:
    django.setup()
