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