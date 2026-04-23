from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.organisations.models import Organisation
from apps.organisations.selectors.organisations import (
    activation_status_for,
    last_invited_at_for,
)


class OrganisationListSerializer(serializers.ModelSerializer[Organisation]):
    total_stores = serializers.IntegerField(read_only=True)
    active_stores = serializers.IntegerField(read_only=True)
    activation_status = serializers.SerializerMethodField()
    last_invited_at = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "org_type",
            "email",
            "address",
            "number_of_stores",
            "status",
            "created_at",
            "total_stores",
            "active_stores",
            "activation_status",
            "last_invited_at",
        ]

    def get_activation_status(self, obj: Organisation) -> str:
        return activation_status_for(obj)

    def get_last_invited_at(self, obj: Organisation) -> str | None:
        ts = last_invited_at_for(obj)
        return ts.isoformat() if ts else None


class OrganisationDetailSerializer(OrganisationListSerializer):
    """Same fields as list — retrieve returns richer attributes later if needed."""


class OrganisationCreateSerializer(serializers.ModelSerializer[Organisation]):
    name = serializers.CharField(min_length=2, max_length=100)
    org_type = serializers.ChoiceField(choices=Organisation.OrgType.choices)
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=Organisation.objects.exclude(status=Organisation.Status.DELETED),
                message="An organisation with this email already exists.",
            )
        ],
    )
    address = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    number_of_stores = serializers.IntegerField(min_value=1, max_value=1000)

    class Meta:
        model = Organisation
        fields: ClassVar[list[str]] = ["name", "org_type", "email", "address", "number_of_stores"]


class OrganisationUpdateSerializer(serializers.ModelSerializer[Organisation]):
    name = serializers.CharField(min_length=2, max_length=100, required=False)
    org_type = serializers.ChoiceField(choices=Organisation.OrgType.choices, required=False)
    address = serializers.CharField(max_length=500, allow_blank=True, required=False)
    number_of_stores = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    status = serializers.ChoiceField(
        choices=[
            (Organisation.Status.ACTIVE.value, "Active"),
            (Organisation.Status.DISABLED.value, "Disabled"),
        ],
        required=False,
    )

    class Meta:
        model = Organisation
        fields: ClassVar[list[str]] = ["name", "org_type", "address", "number_of_stores", "status"]
        # Explicitly NO email here (EORG-02). DRF silently drops unknown fields from
        # the input, so a PATCH body containing email is safe but ignored.
