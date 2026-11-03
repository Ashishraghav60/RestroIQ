from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Membership


def get_active_membership(user, organization_id):
    """The user's active membership in this organization, or None."""
    return (
        Membership.objects.filter(
            user=user,
            organization_id=organization_id,
            status=Membership.Status.ACTIVE,
        )
        .select_related("organization")
        .first()
    )


def roles_that_can_be_invited_by(role):
    """Which roles may someone with `role` invite?"""
    owner = Membership.Role.OWNER.value
    admin = Membership.Role.ADMIN.value
    everything = set(Membership.Role.values)

    if role == owner:
        return everything
    if role == admin:
        return everything - {owner, admin}
    return set()


def require_manager(user, organization_id):
    """Return the caller's membership if they are an owner or admin here.

    Not a member at all -> "not found" (we do not reveal which
    organizations exist). A member without manager rights -> "forbidden".
    """
    membership = get_active_membership(user, organization_id)
    if membership is None:
        raise NotFound("Organization not found.")
    if not roles_that_can_be_invited_by(membership.role):
        raise PermissionDenied("You do not have permission to do this.")
    return membership