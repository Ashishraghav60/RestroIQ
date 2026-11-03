from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .models import Invitation, Membership
from .permissions import get_active_membership, roles_that_can_be_invited_by


def create_invitation(*, inviter, organization_id, email, role):
    """Create an invitation. Returns (invitation, raw_token)."""
    email = email.strip().lower()

    # 1. Is the caller really an active member of this organization?
    membership = get_active_membership(inviter, organization_id)
    if membership is None:
        raise NotFound("Organization not found.")

    # 2. Is the caller allowed to invite someone at this role?
    allowed = roles_that_can_be_invited_by(membership.role)
    if not allowed:
        raise PermissionDenied("You are not allowed to invite people.")
    if role not in allowed:
        raise PermissionDenied("You cannot invite someone with that role.")

    organization = membership.organization

    # 3. Is this person already a member?
    if Membership.objects.filter(
        organization=organization, user__email__iexact=email
    ).exists():
        raise ValidationError(
            {"email": "This person is already a member of the organization."}
        )

    try:
        with transaction.atomic():
            # 4. Deal with an older open invitation for the same email.
            pending = (
                Invitation.objects.select_for_update()
                .filter(
                    organization=organization,
                    email=email,
                    status=Invitation.Status.PENDING,
                )
                .first()
            )
            if pending is not None:
                if pending.is_usable:
                    raise ValidationError(
                        {"email": "An invitation for this email is already open."}
                    )
                # It expired, so retire it and allow a fresh one.
                pending.status = Invitation.Status.REVOKED
                pending.save(update_fields=["status"])

            return Invitation.create_with_token(
                organization=organization,
                email=email,
                role=role,
                invited_by=inviter,
            )
    except IntegrityError:
        # Two requests at the same moment: the database caught the duplicate.
        raise ValidationError(
            {"email": "An invitation for this email is already open."}
        )