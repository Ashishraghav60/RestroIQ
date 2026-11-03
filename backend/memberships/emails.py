import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_invitation_email(invitation, raw_token):
    """Email the invitation link. Returns True if it was sent.

    The token goes after a "#" in the link. Browsers never send that part
    to servers, so it stays out of server logs.
    """
    organization_name = " ".join(invitation.organization.name.split())
    link = (
        f"{settings.FRONTEND_URL.rstrip('/')}"
        f"/accept-invitation#token={raw_token}"
    )
    expires = invitation.expires_at.strftime("%d %B %Y, %H:%M UTC")

    subject = f"You are invited to join {organization_name} on RestroIQ"
    body = (
        f"Hello,\n\n"
        f"You have been invited to join {organization_name} on RestroIQ "
        f"as {invitation.get_role_display()}.\n\n"
        f"Open this link to accept the invitation:\n{link}\n\n"
        f"This invitation expires on {expires}.\n"
        f"If you were not expecting it, you can ignore this email.\n"
    )

    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [invitation.email],
            fail_silently=False,
        )
    except Exception:
        # Do not log the address or the token.
        logger.exception(
            "Could not send invitation email (invitation id %s)", invitation.id
        )
        return False
    return True