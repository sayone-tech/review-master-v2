import factory
from factory.django import DjangoModelFactory

from apps.organisations.models import Organisation


class OrganisationFactory(DjangoModelFactory):
    class Meta:
        model = Organisation
        django_get_or_create = ("email",)

    name = factory.Sequence(lambda n: f"Org {n}")
    email = factory.Sequence(lambda n: f"org{n}@example.com")
    org_type = Organisation.OrgType.RETAIL
    address = factory.Faker("address")
    number_of_stores = 10
    status = Organisation.Status.ACTIVE
