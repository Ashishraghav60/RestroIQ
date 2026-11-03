from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from organizations.models import Organization

from .models import Invitation, Membership

User = get_user_model()

PASSWORD = "Str0ng-Pass-98765!"


class AcceptInvitationTests(APITestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Org A", slug="org-a")
        self.url = reverse("invitation_accept")

    def _invite(self, email="staff@example.com", role=Membership.Role.CASHIER):
        return Invitation.create_with_token(
            organization=self.org, email=email, role=role
        )

    def _accept(self, token, password=PASSWORD):
        payload = {"token": token}
        if password is not None:
            payload["password"] = password
        return self.client.post(self.url, payload, format="json")

    def test_valid_token_creates_account_and_membership(self):
        invitation, raw = self._invite(role=Membership.Role.ACCOUNTANT)

        response = self._accept(raw)

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="staff@example.com")
        membership = Membership.objects.get(user=user, organization=self.org)
        self.assertEqual(membership.role, Membership.Role.ACCOUNTANT)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.ACCEPTED)
        self.assertIsNotNone(invitation.accepted_at)

        login = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "staff@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, 200)

    def test_wrong_token_is_rejected(self):
        self._invite()
        self.assertEqual(self._accept("not-a-real-token").status_code, 400)
        self.assertFalse(User.objects.filter(email="staff@example.com").exists())

    def test_expired_invitation_is_rejected(self):
        invitation, raw = self._invite()
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save()

        self.assertEqual(self._accept(raw).status_code, 400)
        self.assertFalse(User.objects.filter(email="staff@example.com").exists())

    def test_invitation_cannot_be_used_twice(self):
        _, raw = self._invite()
        self.assertEqual(self._accept(raw).status_code, 201)
        self.assertEqual(self._accept(raw).status_code, 400)
        self.assertEqual(Membership.objects.count(), 1)

    def test_revoked_invitation_is_rejected(self):
        invitation, raw = self._invite()
        invitation.status = Invitation.Status.REVOKED
        invitation.save()

        self.assertEqual(self._accept(raw).status_code, 400)

    def test_weak_password_is_rejected_and_invitation_stays_open(self):
        invitation, raw = self._invite()

        response = self._accept(raw, password="123")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="staff@example.com").exists())
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.PENDING)

    def test_existing_account_cannot_be_taken_over_without_login(self):
        existing = User.objects.create_user(
            email="staff@example.com", password=PASSWORD
        )
        _, raw = self._invite()

        response = self._accept(raw, password="Another-Pass-55555!")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Membership.objects.filter(user=existing).exists())
        existing.refresh_from_db()
        self.assertTrue(existing.check_password(PASSWORD))

    def test_existing_user_can_accept_when_logged_in_as_themselves(self):
        existing = User.objects.create_user(
            email="staff@example.com", password=PASSWORD
        )
        _, raw = self._invite()

        self.client.force_authenticate(user=existing)
        response = self._accept(raw, password=None)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Membership.objects.filter(user=existing, organization=self.org).exists()
        )

    def test_logged_in_user_cannot_accept_someone_elses_invitation(self):
        User.objects.create_user(email="staff@example.com", password=PASSWORD)
        other = User.objects.create_user(
            email="other@example.com", password=PASSWORD
        )
        _, raw = self._invite()

        self.client.force_authenticate(user=other)
        response = self._accept(raw, password=None)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Membership.objects.count(), 0)