from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from organizations.models import Organization

from .member_service import ensure_another_active_owner
from .models import Membership

User = get_user_model()

PASSWORD = "Str0ng-Pass-98765!"


class MemberTestBase(APITestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Org A", slug="org-a")
        self.other_org = Organization.objects.create(name="Org B", slug="org-b")

        self.owner = self._member("owner@example.com", Membership.Role.OWNER)
        self.admin = self._member("admin@example.com", Membership.Role.ADMIN)
        self.cashier = self._member("cashier@example.com", Membership.Role.CASHIER)
        self.other_cashier = self._member(
            "cashier-b@example.com", Membership.Role.CASHIER, org=self.other_org
        )
        self.stranger = User.objects.create_user(
            email="stranger@example.com", password=PASSWORD
        )

    def _member(self, email, role, org=None):
        user = User.objects.create_user(email=email, password=PASSWORD)
        Membership.objects.create(
            user=user, organization=org or self.org, role=role
        )
        return user

    def _membership(self, user, org=None):
        return Membership.objects.get(user=user, organization=org or self.org)

    def _url(self, user, org=None):
        org = org or self.org
        return reverse(
            "organization_member_detail",
            args=[org.id, self._membership(user, org).id],
        )

    def _patch(self, actor, target, data, org=None):
        self.client.force_authenticate(user=actor)
        return self.client.patch(self._url(target, org), data, format="json")

    def _delete(self, actor, target, org=None):
        self.client.force_authenticate(user=actor)
        return self.client.delete(self._url(target, org))


class MemberChangeTests(MemberTestBase):

    def test_owner_can_change_a_role(self):
        response = self._patch(self.owner, self.cashier, {"role": "accountant"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._membership(self.cashier).role, "accountant")

    def test_admin_can_change_a_cashier_role(self):
        response = self._patch(self.admin, self.cashier, {"role": "inventory_manager"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._membership(self.cashier).role, "inventory_manager")

    def test_admin_cannot_promote_someone_to_admin(self):
        response = self._patch(self.admin, self.cashier, {"role": "admin"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._membership(self.cashier).role, "cashier")

    def test_admin_cannot_change_an_owner(self):
        response = self._patch(self.admin, self.owner, {"role": "cashier"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._membership(self.owner).role, "owner")

    def test_admin_cannot_change_another_admin(self):
        other_admin = self._member("admin2@example.com", Membership.Role.ADMIN)

        response = self._patch(self.admin, other_admin, {"role": "cashier"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._membership(other_admin).role, "admin")

    def test_cashier_cannot_change_roles(self):
        other = self._member("kitchen@example.com", Membership.Role.KITCHEN_STAFF)

        response = self._patch(self.cashier, other, {"role": "cashier"})

        self.assertEqual(response.status_code, 403)

    def test_stranger_gets_not_found(self):
        response = self._patch(self.stranger, self.cashier, {"role": "accountant"})
        self.assertEqual(response.status_code, 404)

    def test_cannot_change_own_membership(self):
        response = self._patch(self.owner, self.owner, {"role": "cashier"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._membership(self.owner).role, "owner")

    def test_membership_of_another_organization_is_not_found(self):
        # Our own organization's URL, but another organization's member id.
        other_membership = self._membership(self.other_cashier, self.other_org)
        url = reverse(
            "organization_member_detail",
            args=[self.org.id, other_membership.id],
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(url, {"role": "accountant"}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self._membership(self.other_cashier, self.other_org).role, "cashier"
        )

    def test_suspending_blocks_access_immediately(self):
        response = self._patch(self.owner, self.admin, {"status": "suspended"})
        self.assertEqual(response.status_code, 200)

        # The suspended admin's login still works, but it grants nothing.
        self.client.force_authenticate(user=self.admin)
        members = self.client.get(
            reverse("organization_member_list", args=[self.org.id])
        )
        self.assertEqual(members.status_code, 404)

        me = self.client.get(reverse("me"))
        self.assertEqual(me.data["memberships"], [])

    def test_member_can_be_reactivated(self):
        self._patch(self.owner, self.cashier, {"status": "suspended"})
        response = self._patch(self.owner, self.cashier, {"status": "active"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._membership(self.cashier).status, "active")

    def test_empty_request_is_rejected(self):
        self.assertEqual(self._patch(self.owner, self.cashier, {}).status_code, 400)

    def test_unknown_role_is_rejected(self):
        response = self._patch(self.owner, self.cashier, {"role": "emperor"})
        self.assertEqual(response.status_code, 400)

    def test_owner_can_demote_another_owner(self):
        second_owner = self._member("owner2@example.com", Membership.Role.OWNER)

        response = self._patch(self.owner, second_owner, {"role": "admin"})

        self.assertEqual(response.status_code, 200)
        active_owners = Membership.objects.filter(
            organization=self.org, role="owner", status="active"
        )
        self.assertEqual(active_owners.count(), 1)

    def test_login_is_required(self):
        url = self._url(self.cashier)
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.patch(url, {"role": "accountant"}, format="json").status_code,
            401,
        )


class MemberRemovalTests(MemberTestBase):

    def test_owner_can_remove_a_member_but_the_account_stays(self):
        response = self._delete(self.owner, self.cashier)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Membership.objects.filter(user=self.cashier, organization=self.org).exists()
        )
        self.assertTrue(User.objects.filter(pk=self.cashier.pk).exists())

    def test_admin_can_remove_a_cashier(self):
        self.assertEqual(self._delete(self.admin, self.cashier).status_code, 204)

    def test_admin_cannot_remove_another_admin(self):
        other_admin = self._member("admin2@example.com", Membership.Role.ADMIN)

        response = self._delete(self.admin, other_admin)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Membership.objects.filter(user=other_admin, organization=self.org).exists()
        )

    def test_owner_cannot_remove_themselves(self):
        response = self._delete(self.owner, self.owner)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Membership.objects.filter(user=self.owner, organization=self.org).exists()
        )

    def test_cashier_cannot_remove_anyone(self):
        other = self._member("kitchen@example.com", Membership.Role.KITCHEN_STAFF)
        self.assertEqual(self._delete(self.cashier, other).status_code, 403)

    def test_member_of_another_organization_is_not_found(self):
        other_membership = self._membership(self.other_cashier, self.other_org)
        url = reverse(
            "organization_member_detail",
            args=[self.org.id, other_membership.id],
        )

        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(
            Membership.objects.filter(pk=other_membership.pk).exists()
        )


class LastOwnerRuleTests(TestCase):
    """The API blocks self-changes, so these test the safety check directly."""

    def setUp(self):
        self.org = Organization.objects.create(name="Org A", slug="org-a")

    def _owner(self, email):
        user = User.objects.create_user(email=email, password=PASSWORD)
        return Membership.objects.create(
            user=user, organization=self.org, role=Membership.Role.OWNER
        )

    def test_sole_owner_cannot_be_removed(self):
        only_owner = self._owner("owner@example.com")

        with self.assertRaises(ValidationError):
            ensure_another_active_owner(self.org.id, only_owner)

    def test_owner_can_go_when_another_active_owner_exists(self):
        first = self._owner("owner1@example.com")
        self._owner("owner2@example.com")

        ensure_another_active_owner(self.org.id, first)

    def test_a_suspended_owner_does_not_count(self):
        first = self._owner("owner1@example.com")
        second = self._owner("owner2@example.com")
        second.status = Membership.Status.SUSPENDED
        second.save()

        with self.assertRaises(ValidationError):
            ensure_another_active_owner(self.org.id, first)