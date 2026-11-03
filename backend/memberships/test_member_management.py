from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from organizations.models import Organization

from .models import Invitation, Membership

User = get_user_model()

PASSWORD = "Str0ng-Pass-98765!"


class ManagementTestBase(APITestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Org A", slug="org-a")
        self.other_org = Organization.objects.create(name="Org B", slug="org-b")

        self.owner = self._member("owner@example.com", Membership.Role.OWNER)
        self.admin = self._member("admin@example.com", Membership.Role.ADMIN)
        self.cashier = self._member("cashier@example.com", Membership.Role.CASHIER)
        self._member("boss-b@example.com", Membership.Role.OWNER, org=self.other_org)
        self.stranger = User.objects.create_user(
            email="stranger@example.com", password=PASSWORD
        )

    def _member(self, email, role, org=None):
        user = User.objects.create_user(email=email, password=PASSWORD)
        Membership.objects.create(
            user=user, organization=org or self.org, role=role
        )
        return user

    def _invitation(self, email, role="cashier", org=None):
        return Invitation.create_with_token(
            organization=org or self.org, email=email, role=role
        )

    def _list_url(self, org=None):
        return reverse("organization_invitation_create", args=[(org or self.org).id])

    def _revoke_url(self, invitation, org=None):
        return reverse(
            "organization_invitation_revoke",
            args=[(org or self.org).id, invitation.id],
        )

    def _members_url(self, org=None):
        return reverse("organization_member_list", args=[(org or self.org).id])


class InvitationListTests(ManagementTestBase):

    def test_owner_sees_only_open_invitations_of_own_organization(self):
        self._invitation("open@example.com")

        revoked, _ = self._invitation("revoked@example.com")
        revoked.status = Invitation.Status.REVOKED
        revoked.save()

        expired, _ = self._invitation("expired@example.com")
        expired.expires_at = timezone.now() - timedelta(minutes=1)
        expired.save()

        self._invitation("elsewhere@example.com", org=self.other_org)

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self._list_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual([i["email"] for i in response.data], ["open@example.com"])

    def test_list_never_exposes_secrets(self):
        self._invitation("open@example.com")

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self._list_url())

        self.assertNotIn("token", response.data[0])
        self.assertNotIn("token_hash", response.data[0])

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(self._list_url()).status_code, 200)

    def test_cashier_cannot_list(self):
        self.client.force_authenticate(user=self.cashier)
        self.assertEqual(self.client.get(self._list_url()).status_code, 403)

    def test_stranger_gets_not_found(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(self.client.get(self._list_url()).status_code, 404)

    def test_login_is_required(self):
        self.assertEqual(self.client.get(self._list_url()).status_code, 401)


class RevokeInvitationTests(ManagementTestBase):

    def test_owner_revokes_and_token_stops_working(self):
        invitation, raw = self._invitation("new@example.com")

        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(self._revoke_url(invitation))

        self.assertEqual(response.status_code, 204)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.REVOKED)

        self.client.force_authenticate(user=None)
        accept = self.client.post(
            reverse("invitation_accept"),
            {"token": raw, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(accept.status_code, 400)

    def test_admin_can_revoke_a_cashier_invitation(self):
        invitation, _ = self._invitation("new@example.com", role="cashier")

        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete(self._revoke_url(invitation)).status_code, 204)

    def test_admin_cannot_revoke_an_admin_invitation(self):
        invitation, _ = self._invitation("new@example.com", role="admin")

        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self._revoke_url(invitation))

        self.assertEqual(response.status_code, 403)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.PENDING)

    def test_cashier_cannot_revoke(self):
        invitation, _ = self._invitation("new@example.com")

        self.client.force_authenticate(user=self.cashier)
        self.assertEqual(self.client.delete(self._revoke_url(invitation)).status_code, 403)

    def test_invitation_of_another_organization_is_not_found(self):
        invitation, _ = self._invitation("new@example.com", org=self.other_org)

        self.client.force_authenticate(user=self.owner)
        # Our own organization's URL, but someone else's invitation id.
        response = self.client.delete(self._revoke_url(invitation, org=self.org))

        self.assertEqual(response.status_code, 404)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.PENDING)

    def test_accepted_invitation_cannot_be_revoked(self):
        invitation, _ = self._invitation("new@example.com")
        invitation.status = Invitation.Status.ACCEPTED
        invitation.save()

        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.delete(self._revoke_url(invitation)).status_code, 400)


class MemberListTests(ManagementTestBase):

    def test_owner_sees_members_of_own_organization_only(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self._members_url())

        self.assertEqual(response.status_code, 200)
        emails = {m["email"] for m in response.data}
        self.assertEqual(
            emails,
            {"owner@example.com", "admin@example.com", "cashier@example.com"},
        )

    def test_member_list_does_not_expose_passwords(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self._members_url())

        self.assertNotIn("password", response.data[0])

    def test_cashier_cannot_list_members(self):
        self.client.force_authenticate(user=self.cashier)
        self.assertEqual(self.client.get(self._members_url()).status_code, 403)

    def test_stranger_gets_not_found(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(self.client.get(self._members_url()).status_code, 404)

    def test_login_is_required(self):
        self.assertEqual(self.client.get(self._members_url()).status_code, 401)