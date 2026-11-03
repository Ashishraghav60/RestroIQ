from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from organizations.models import Organization

from .models import Invitation, Membership

User = get_user_model()

PASSWORD = "Str0ng-Pass-98765!"


class CreateInvitationTests(APITestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Org A", slug="org-a")
        self.other_org = Organization.objects.create(name="Org B", slug="org-b")

        self.owner = self._member("owner@example.com", Membership.Role.OWNER)
        self.admin = self._member("admin@example.com", Membership.Role.ADMIN)
        self.cashier = self._member("cashier@example.com", Membership.Role.CASHIER)

    def _member(self, email, role, org=None, status=Membership.Status.ACTIVE):
        user = User.objects.create_user(email=email, password=PASSWORD)
        Membership.objects.create(
            user=user, organization=org or self.org, role=role, status=status
        )
        return user

    def _url(self, org=None):
        return reverse(
            "organization_invitation_create",
            args=[(org or self.org).id],
        )

    def _invite(self, user, email="new@example.com", role="cashier", org=None):
        self.client.force_authenticate(user=user)
        return self.client.post(
            self._url(org), {"email": email, "role": role}, format="json"
        )

    # ---- who may invite ----

    def test_owner_can_invite_and_the_token_works(self):
        response = self._invite(self.owner, role="accountant")

        self.assertEqual(response.status_code, 201)
        self.assertIn("token", response.data)
        invitation = Invitation.objects.get(email="new@example.com")
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertEqual(invitation.role, "accountant")

        # The invited person can now accept it.
        self.client.force_authenticate(user=None)
        accept = self.client.post(
            reverse("invitation_accept"),
            {"token": response.data["token"], "password": PASSWORD},
            format="json",
        )
        self.assertEqual(accept.status_code, 201)

    def test_admin_can_invite_a_cashier(self):
        self.assertEqual(self._invite(self.admin, role="cashier").status_code, 201)

    def test_admin_cannot_invite_an_owner(self):
        self.assertEqual(self._invite(self.admin, role="owner").status_code, 403)

    def test_admin_cannot_invite_another_admin(self):
        self.assertEqual(self._invite(self.admin, role="admin").status_code, 403)

    def test_cashier_cannot_invite_anyone(self):
        self.assertEqual(self._invite(self.cashier).status_code, 403)
        self.assertFalse(Invitation.objects.exists())

    # ---- organization isolation ----

    def test_non_member_gets_not_found(self):
        stranger = User.objects.create_user(
            email="stranger@example.com", password=PASSWORD
        )
        self.assertEqual(self._invite(stranger).status_code, 404)

    def test_owner_of_one_organization_cannot_invite_into_another(self):
        response = self._invite(self.owner, org=self.other_org)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Invitation.objects.exists())

    def test_suspended_owner_cannot_invite(self):
        suspended = self._member(
            "suspended@example.com",
            Membership.Role.OWNER,
            status=Membership.Status.SUSPENDED,
        )
        self.assertEqual(self._invite(suspended).status_code, 404)

    def test_login_is_required(self):
        response = self.client.post(
            self._url(),
            {"email": "new@example.com", "role": "cashier"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    # ---- duplicates and bad input ----

    def test_cannot_invite_someone_who_is_already_a_member(self):
        response = self._invite(self.owner, email="cashier@example.com")
        self.assertEqual(response.status_code, 400)

    def test_cannot_create_a_second_open_invitation_for_same_email(self):
        self.assertEqual(self._invite(self.owner).status_code, 201)
        self.assertEqual(self._invite(self.owner).status_code, 400)

    def test_expired_invitation_is_replaced_by_a_new_one(self):
        old, _ = Invitation.create_with_token(
            organization=self.org,
            email="new@example.com",
            role=Membership.Role.CASHIER,
        )
        old.expires_at = timezone.now() - timedelta(minutes=1)
        old.save()

        self.assertEqual(self._invite(self.owner).status_code, 201)

        old.refresh_from_db()
        self.assertEqual(old.status, Invitation.Status.REVOKED)

    def test_unknown_role_is_rejected(self):
        self.assertEqual(self._invite(self.owner, role="emperor").status_code, 400)

    def test_bad_email_is_rejected(self):
        self.assertEqual(self._invite(self.owner, email="not-an-email").status_code, 400)