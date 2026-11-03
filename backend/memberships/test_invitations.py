from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization

from .models import Invitation, Membership


class InvitationTests(TestCase):

    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A", slug="org-a")
        self.org_b = Organization.objects.create(name="Org B", slug="org-b")

    def _invite(self, org=None, email="staff@example.com"):
        return Invitation.create_with_token(
            organization=org or self.org_a,
            email=email,
            role=Membership.Role.CASHIER,
        )

    def test_raw_token_is_not_stored(self):
        invitation, raw = self._invite()
        self.assertNotEqual(invitation.token_hash, raw)
        self.assertEqual(len(invitation.token_hash), 64)

    def test_hash_of_raw_token_matches_stored_hash(self):
        invitation, raw = self._invite()
        self.assertEqual(Invitation.hash_token(raw), invitation.token_hash)

    def test_email_is_saved_in_lowercase(self):
        invitation, _ = self._invite(email="  Staff@Example.COM ")
        self.assertEqual(invitation.email, "staff@example.com")

    def test_second_pending_invite_for_same_email_and_org_rejected(self):
        self._invite()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._invite()

    def test_new_invite_allowed_after_old_one_is_revoked(self):
        old, _ = self._invite()
        old.status = Invitation.Status.REVOKED
        old.save()
        new, _ = self._invite()
        self.assertEqual(new.status, Invitation.Status.PENDING)

    def test_same_email_can_be_invited_to_two_organizations(self):
        self._invite(org=self.org_a)
        self._invite(org=self.org_b)
        self.assertEqual(Invitation.objects.count(), 2)

    def test_invitation_expires(self):
        invitation, _ = self._invite()
        self.assertTrue(invitation.is_usable)

        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save()
        self.assertTrue(invitation.is_expired)
        self.assertFalse(invitation.is_usable)