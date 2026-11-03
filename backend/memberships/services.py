from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from .models import Invitation, Membership

User = get_user_model()

# One message for every "bad token" case, so attackers learn nothing.
INVALID_MESSAGE = "This invitation is invalid or has expired."


class InvitationError(Exception):
    """Raised when an invitation cannot be accepted."""


def accept_invitation(
    *,
    raw_token,
    password=None,
    first_name="",
    last_name="",
    acting_user=None,
):
    """Accept an invitation. Returns the new Membership.

    Everything happens in one transaction, and the invitation row is
    locked, so two people cannot accept the same invitation at once.
    """
    token_hash = Invitation.hash_token(raw_token)

    with transaction.atomic():
        invitation = (
            Invitation.objects.select_for_update()
            .select_related("organization")
            .filter(token_hash=token_hash)
            .first()
        )
        if invitation is None or not invitation.is_usable:
            raise InvitationError(INVALID_MESSAGE)

        existing = User.objects.filter(email__iexact=invitation.email).first()

        if existing is not None:
            # Never let an invitation change an existing account.
            if not existing.is_active:
                raise InvitationError(INVALID_MESSAGE)
            if acting_user is None or acting_user.pk != existing.pk:
                raise InvitationError(
                    "An account with this email already exists. "
                    "Please log in with it first, then accept the invitation."
                )
            if Membership.objects.filter(
                user=existing, organization=invitation.organization
            ).exists():
                raise InvitationError(
                    "You are already a member of this organization."
                )
            user = existing
        else:
            if not password:
                raise InvitationError("A password is required.")

            candidate = User(
                email=invitation.email,
                first_name=first_name,
                last_name=last_name,
            )
            try:
                validate_password(password, user=candidate)
            except DjangoValidationError as exc:
                raise InvitationError(" ".join(exc.messages))

            user = User.objects.create_user(
                email=invitation.email, password=password
            )
            user.first_name = first_name
            user.last_name = last_name
            user.save()

        membership = Membership.objects.create(
            user=user,
            organization=invitation.organization,
            role=invitation.role,
        )

        invitation.status = Invitation.Status.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_at"])

    return membership