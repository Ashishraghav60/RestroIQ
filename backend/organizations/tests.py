from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from .models import Branch, Brand, Organization, Region


class OrganizationHierarchyTests(TestCase):

    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A", slug="org-a")
        self.org_b = Organization.objects.create(name="Org B", slug="org-b")

        self.brand_a = Brand.objects.create(
            organization=self.org_a, name="Burger House", slug="burger-house"
        )
        self.brand_b = Brand.objects.create(
            organization=self.org_b, name="Burger House", slug="burger-house"
        )

        self.region_a = Region.objects.create(
            brand=self.brand_a, name="North", slug="north"
        )

    # ---- Brand ----

    def test_same_brand_slug_allowed_in_different_organizations(self):
        self.assertEqual(Brand.objects.filter(slug="burger-house").count(), 2)

    def test_duplicate_brand_slug_in_same_organization_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Brand.objects.create(
                    organization=self.org_a, name="Copy", slug="burger-house"
                )

    # ---- Region ----

    def test_region_organization_is_filled_from_brand(self):
        self.assertEqual(self.region_a.organization_id, self.org_a.id)

    def test_region_rejects_brand_from_another_organization(self):
        with self.assertRaises(ValidationError):
            Region.objects.create(
                organization=self.org_a,
                brand=self.brand_b,
                name="Wrong",
                slug="wrong",
            )

    def test_region_slug_unique_within_brand_only(self):
        other_brand = Brand.objects.create(
            organization=self.org_a, name="Pizza Corner", slug="pizza-corner"
        )
        Region.objects.create(brand=other_brand, name="North", slug="north")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Region.objects.create(
                    brand=self.brand_a, name="North 2", slug="north"
                )

    # ---- Branch ----

    def test_branch_organization_is_filled_from_region(self):
        branch = Branch.objects.create(
            region=self.region_a, name="Delhi", slug="delhi"
        )
        self.assertEqual(branch.organization_id, self.org_a.id)
        self.assertEqual(branch.brand, self.brand_a)

    def test_branch_rejects_region_from_another_organization(self):
        with self.assertRaises(ValidationError):
            Branch.objects.create(
                organization=self.org_b,
                region=self.region_a,
                name="Wrong",
                slug="wrong",
            )

    def test_branch_slug_unique_within_organization(self):
        Branch.objects.create(region=self.region_a, name="Delhi", slug="delhi")
        other_region = Region.objects.create(
            brand=self.brand_a, name="South", slug="south"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Branch.objects.create(
                    region=other_region, name="Delhi 2", slug="delhi"
                )

    def test_branch_timezone_falls_back_to_organization(self):
        branch = Branch.objects.create(
            region=self.region_a, name="Delhi", slug="delhi"
        )
        self.assertEqual(branch.effective_timezone, "Asia/Kolkata")

        branch.timezone = "Asia/Dubai"
        self.assertEqual(branch.effective_timezone, "Asia/Dubai")

    # ---- Delete protection ----

    def test_cannot_delete_brand_that_still_has_regions(self):
        with self.assertRaises(ProtectedError):
            self.brand_a.delete()