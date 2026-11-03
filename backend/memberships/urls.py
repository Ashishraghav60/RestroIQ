from django.urls import path

from .views import AcceptInvitationView

urlpatterns = [
    path(
        "invitations/accept/",
        AcceptInvitationView.as_view(),
        name="invitation_accept",
    ),
]