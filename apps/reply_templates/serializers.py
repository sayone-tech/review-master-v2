from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.reply_templates.models import ReplyTemplate


class ReplyTemplateReadSerializer(serializers.ModelSerializer[ReplyTemplate]):
    class Meta:
        model = ReplyTemplate
        fields: ClassVar[list[str]] = ["id", "name", "content", "created_at"]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at"]


class ReplyTemplateCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=1, max_length=100)
    content = serializers.CharField(min_length=1)


class ReplyTemplateUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=1, max_length=100, required=False)
    content = serializers.CharField(min_length=1, required=False)
