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


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    # Only needed when the person has no account yet.
    password = serializers.CharField(
        write_only=True,
        required=False,
        trim_whitespace=False,
        max_length=128,
    )
    first_name = serializers.CharField(
        required=False, allow_blank=True, max_length=30
    )
    last_name = serializers.CharField(
        required=False, allow_blank=True, max_length=30
    )


class CreateInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=Membership.Role.choices)