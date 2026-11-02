from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from organizations.models import Branch, Brand, Organization, Region

from .models import BranchAssignment, Membership

User = get_user_model()


class MembershipTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="chef@example.com", password="test-pass-12345"
        )
        self.org_a = Organization.objects.create(name="Org A", slug="org-a")
        self.org_b = Organization.objects.create(name="Org B", slug="org-b")

        brand = Brand.objects.create(
            organization=self.org_a, name="Burger House", slug="burger-house"
        )
        region = Region.objects.create(brand=brand, name="North", slug="north")
        self.branch_a = Branch.objects.create(
            region=region, name="Delhi", slug="delhi"
        )

    def test_default_role_is_cashier_and_active(self):
        m = Membership.objects.create(user=self.user, organization=self.org_a)
        self.assertEqual(m.role, Membership.Role.CASHIER)
        self.assertEqual(m.status, Membership.Status.ACTIVE)

    def test_user_can_belong_to_several_organizations_with_different_roles(self):
        Membership.objects.create(
            user=self.user, organization=self.org_a, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.user,
            organization=self.org_b,
            role=Membership.Role.ACCOUNTANT,
        )
        self.assertEqual(self.user.memberships.count(), 2)

    def test_duplicate_membership_in_same_organization_rejected(self):
        Membership.objects.create(user=self.user, organization=self.org_a)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Membership.objects.create(
                    user=self.user, organization=self.org_a
                )

    def test_branch_assignment_fills_organization_from_membership(self):
        m = Membership.objects.create(user=self.user, organization=self.org_a)
        a = BranchAssignment.objects.create(membership=m, branch=self.branch_a)
        self.assertEqual(a.organization_id, self.org_a.id)

    def test_branch_assignment_rejects_branch_from_another_organization(self):
        m = Membership.objects.create(user=self.user, organization=self.org_b)
        with self.assertRaises(ValidationError):
            BranchAssignment.objects.create(membership=m, branch=self.branch_a)

    def test_same_branch_cannot_be_assigned_twice(self):
        m = Membership.objects.create(user=self.user, organization=self.org_a)
        BranchAssignment.objects.create(membership=m, branch=self.branch_a)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BranchAssignment.objects.create(
                    membership=m, branch=self.branch_a
                )