from rest_framework import serializers

from .models import Membership


class AssignedBranchSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="branch.id", read_only=True)
    name = serializers.CharField(source="branch.name", read_only=True)


class MembershipSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(
        source="organization.id", read_only=True
    )
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )
    organization_slug = serializers.CharField(
        source="organization.slug", read_only=True
    )
    branches = AssignedBranchSerializer(
        source="branch_assignments", many=True, read_only=True
    )

    class Meta:
        model = Membership
        fields = (
            "id",
            "organization_id",
            "organization_name",
            "organization_slug",
            "role",
            "status",
            "branches",
        )
        read_only_fields = fields