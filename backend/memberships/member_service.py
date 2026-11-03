from django.db import transaction
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


def ensure_another_active_owner(organization_id, excluding):
    """Raise unless the organization has another active owner.

    The owner rows are locked, so two requests at the same moment cannot
    both remove "the other" owner. Must be called inside a transaction.
    """
    others = list(
        Membership.objects.select_for_update(of=("self",))
        .filter(
            organization_id=organization_id,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )
        .exclude(pk=excluding.pk)
        .order_by("pk")
        .only("id")
    )
    if not others:
        raise ValidationError(
            {"detail": "An organization must keep at least one active owner."}
        )


def _get_manageable_target(*, user, organization_id, membership_id):
    """Check the caller's rights and return (manager, locked target)."""
    manager = require_manager(user, organization_id)

    # Looked up inside the caller's own organization only.
    target = (
        Membership.objects.select_for_update(of=("self",))
        .select_related("user")
        .filter(id=membership_id, organization=manager.organization)
        .order_by("pk")
        .first()
    )
    if target is None:
        raise NotFound("Member not found.")

    if target.pk == manager.pk:
        raise PermissionDenied("You cannot change your own membership.")

    # You can only manage people at roles you are allowed to invite.
    if target.role not in roles_that_can_be_invited_by(manager.role):
        raise PermissionDenied("You cannot manage this member.")

    return manager, target


def update_member(
    *, user, organization_id, membership_id, role=None, status=None
):
    with transaction.atomic():
        manager, target = _get_manageable_target(
            user=user,
            organization_id=organization_id,
            membership_id=membership_id,
        )

        allowed = roles_that_can_be_invited_by(manager.role)
        new_role = role if role is not None else target.role
        new_status = status if status is not None else target.status

        if new_role not in allowed:
            raise PermissionDenied("You cannot assign that role.")

        is_active_owner = (
            target.role == Membership.Role.OWNER
            and target.status == Membership.Status.ACTIVE
        )
        stops_being_active_owner = (
            new_role != Membership.Role.OWNER
            or new_status != Membership.Status.ACTIVE
        )
        if is_active_owner and stops_being_active_owner:
            ensure_another_active_owner(target.organization_id, target)

        target.role = new_role
        target.status = new_status
        target.save(update_fields=["role", "status", "updated_at"])
        return target


def remove_member(*, user, organization_id, membership_id):
    with transaction.atomic():
        manager, target = _get_manageable_target(
            user=user,
            organization_id=organization_id,
            membership_id=membership_id,
        )

        if (
            target.role == Membership.Role.OWNER
            and target.status == Membership.Status.ACTIVE
        ):
            ensure_another_active_owner(target.organization_id, target)

        # Their account stays. Only the link to this organization goes.
        target.delete()