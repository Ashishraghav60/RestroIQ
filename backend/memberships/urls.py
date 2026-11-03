from django.urls import path

from .views import AcceptInvitationView, CreateInvitationView

urlpatterns = [
    path(
        "invitations/accept/",
        AcceptInvitationView.as_view(),
        name="invitation_accept",
    ),
    path(
        "organizations/<uuid:organization_id>/invitations/",
        CreateInvitationView.as_view(),
        name="organization_invitation_create",
    ),
]