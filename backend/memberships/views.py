from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .emails import send_invitation_email
from .invitation_service import create_invitation
from .member_service import (
    list_members,
    list_pending_invitations,
    remove_member,
    revoke_invitation,
    update_member,
)
from .serializers import (
    AcceptInvitationSerializer,
    CreateInvitationSerializer,
    InvitationSerializer,
    MemberSerializer,
    UpdateMemberSerializer,
)
from .services import InvitationError, accept_invitation


class AcceptInvitationThrottle(AnonRateThrottle):
    # Slows down people who try to guess tokens.
    scope = "accept_invitation"
    rate = "20/hour"


class CreateInvitationThrottle(UserRateThrottle):
    scope = "create_invitation"
    rate = "30/hour"


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


class CreateInvitationView(APIView):
    """GET lists open invitations; POST creates one. Owners and admins only."""

    throttle_classes = [CreateInvitationThrottle]

    def get_throttles(self):
        # Only creating is rate-limited. Reading the list is not.
        if self.request.method == "POST":
            return super().get_throttles()
        return []

    @extend_schema(responses=InvitationSerializer(many=True))
    def get(self, request, organization_id):
        invitations = list_pending_invitations(
            user=request.user, organization_id=organization_id
        )
        return Response(InvitationSerializer(invitations, many=True).data)

    @extend_schema(
        request=CreateInvitationSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request, organization_id):
        serializer = CreateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        invitation, raw_token = create_invitation(
            inviter=request.user,
            organization_id=organization_id,
            email=data["email"],
            role=data["role"],
        )

        # The secret token only travels by email. It is never returned here.
        email_sent = send_invitation_email(invitation, raw_token)

        return Response(
            {
                "id": str(invitation.id),
                "email": invitation.email,
                "role": invitation.role,
                "expires_at": invitation.expires_at,
                "email_sent": email_sent,
            },
            status=201,
        )


class RevokeInvitationView(APIView):
    """Cancel an open invitation."""

    @extend_schema(responses={204: None})
    def delete(self, request, organization_id, invitation_id):
        revoke_invitation(
            user=request.user,
            organization_id=organization_id,
            invitation_id=invitation_id,
        )
        return Response(status=204)


class MemberListView(APIView):
    """List the members of an organization. Owners and admins only."""

    @extend_schema(responses=MemberSerializer(many=True))
    def get(self, request, organization_id):
        members = list_members(
            user=request.user, organization_id=organization_id
        )
        return Response(MemberSerializer(members, many=True).data)


class MemberDetailView(APIView):
    """PATCH changes a member's role or status. DELETE removes them."""

    @extend_schema(
        request=UpdateMemberSerializer,
        responses=MemberSerializer,
    )
    def patch(self, request, organization_id, membership_id):
        serializer = UpdateMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        member = update_member(
            user=request.user,
            organization_id=organization_id,
            membership_id=membership_id,
            role=data.get("role"),
            status=data.get("status"),
        )
        return Response(MemberSerializer(member).data)

    @extend_schema(responses={204: None})
    def delete(self, request, organization_id, membership_id):
        remove_member(
            user=request.user,
            organization_id=organization_id,
            membership_id=membership_id,
        )
        return Response(status=204)