from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .serializers import AcceptInvitationSerializer
from .services import InvitationError, accept_invitation


class AcceptInvitationThrottle(AnonRateThrottle):
    # Slows down people who try to guess tokens.
    scope = "accept_invitation"
    rate = "20/hour"


class AcceptInvitationView(APIView):
    """Public endpoint: anyone holding a valid token may use it."""

    permission_classes = [AllowAny]
    throttle_classes = [AcceptInvitationThrottle]

    @extend_schema(
        request=AcceptInvitationSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        acting_user = request.user if request.user.is_authenticated else None

        try:
            membership = accept_invitation(
                raw_token=data["token"],
                password=data.get("password"),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                acting_user=acting_user,
            )
        except InvitationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {
                "detail": "Invitation accepted. You can now log in.",
                "organization": membership.organization.name,
                "role": membership.role,
            },
            status=201,
        )