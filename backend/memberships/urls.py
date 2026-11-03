from django.urls import path

from .views import (
    AcceptInvitationView,
    CreateInvitationView,
    MemberDetailView,
    MemberListView,
    RevokeInvitationView,
)

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
    path(
        "organizations/<uuid:organization_id>/invitations/<uuid:invitation_id>/",
        RevokeInvitationView.as_view(),
        name="organization_invitation_revoke",
    ),
    path(
        "organizations/<uuid:organization_id>/members/",
        MemberListView.as_view(),
        name="organization_member_list",
    ),
    path(
        "organizations/<uuid:organization_id>/members/<uuid:membership_id>/",
        MemberDetailView.as_view(),
        name="organization_member_detail",
    ),
]