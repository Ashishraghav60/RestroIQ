from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from memberships.models import Membership

from .serializers import MeSerializer


class MeView(APIView):
    """Returns the logged-in user and their active memberships."""

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        memberships = (
            Membership.objects.filter(
                user=request.user,
                status=Membership.Status.ACTIVE,
            )
            .select_related("organization")
            .prefetch_related("branch_assignments__branch")
        )
        serializer = MeSerializer(
            {"user": request.user, "memberships": memberships}
        )
        return Response(serializer.data)