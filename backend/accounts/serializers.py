from django.contrib.auth import get_user_model
from rest_framework import serializers

from memberships.serializers import MembershipSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")
        read_only_fields = fields


class MeSerializer(serializers.Serializer):
    user = UserSerializer(read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)