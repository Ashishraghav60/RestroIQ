from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .models import Invitation, Membership
from .permissions import require_manager, roles_that_can_be_invited_by


def list_pending_invitations(*, user, organization_id):
    manager = require_manager(user, organization_id)
    return Invitation.objects.filter(
        organization=manager.organization,
        status=Invitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    )


def revoke_invitation(*, user, organization_id, invitation_id):
    manager = require_manager(user, organization_id)

    # Looked up inside the caller's own organization only.
    invitation = Invitation.objects.filter(
        id=invitation_id, organization=manager.organization
    ).first()
    if invitation is None:
        raise NotFound("Invitation not found.")

    # Same rule as creating: you cannot touch invitations above your level.
    if invitation.role not in roles_that_can_be_invited_by(manager.role):
        raise PermissionDenied("You cannot revoke this invitation.")

    if invitation.status != Invitation.Status.PENDING:
        raise ValidationError(
            {"detail": "Only open invitations can be revoked."}
        )

    invitation.status = Invitation.Status.REVOKED
    invitation.save(update_fields=["status"])
    return invitation


def list_members(*, user, organization_id):
    manager = require_manager(user, organization_id)
    return (
        Membership.objects.filter(organization=manager.organization)
        .select_related("user")
        .order_by("user__email")
    )