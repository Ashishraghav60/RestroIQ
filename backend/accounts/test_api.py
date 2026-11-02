from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from memberships.models import BranchAssignment, Membership
from organizations.models import Branch, Brand, Organization, Region

User = get_user_model()

PASSWORD = "test-pass-12345"


class AuthTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="chef@example.com", password=PASSWORD
        )

    def _login(self, email="chef@example.com", password=PASSWORD):
        return self.client.post(
            reverse("token_obtain_pair"),
            {"email": email, "password": password},
            format="json",
        )

    def test_login_returns_access_and_refresh_tokens(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_is_rejected(self):
        response = self._login(password="wrong-password")
        self.assertEqual(response.status_code, 401)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self._login().status_code, 401)

    def test_refresh_rotates_token_and_blacklists_the_old_one(self):
        old_refresh = self._login().data["refresh"]

        first = self.client.post(
            reverse("token_refresh"), {"refresh": old_refresh}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        self.assertNotEqual(first.data["refresh"], old_refresh)

        reuse = self.client.post(
            reverse("token_refresh"), {"refresh": old_refresh}, format="json"
        )
        self.assertEqual(reuse.status_code, 401)

    def test_blacklisted_refresh_token_cannot_be_used(self):
        refresh = self._login().data["refresh"]

        out = self.client.post(
            reverse("token_blacklist"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(out.status_code, 200)

        again = self.client.post(
            reverse("token_refresh"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(again.status_code, 401)


class MeEndpointTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="chef@example.com", password=PASSWORD
        )
        self.other = User.objects.create_user(
            email="other@example.com", password=PASSWORD
        )
        self.org_a = Organization.objects.create(name="Org A", slug="org-a")
        self.org_b = Organization.objects.create(name="Org B", slug="org-b")

        brand = Brand.objects.create(
            organization=self.org_a, name="Burger House", slug="burger-house"
        )
        region = Region.objects.create(brand=brand, name="North", slug="north")
        self.branch = Branch.objects.create(
            region=region, name="Delhi", slug="delhi"
        )

    def _authenticate(self, user):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": user.email, "password": PASSWORD},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_me_returns_user_and_memberships(self):
        m = Membership.objects.create(
            user=self.user,
            organization=self.org_a,
            role=Membership.Role.BRANCH_MANAGER,
        )
        BranchAssignment.objects.create(membership=m, branch=self.branch)

        self._authenticate(self.user)
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["email"], "chef@example.com")
        self.assertEqual(len(response.data["memberships"]), 1)

        membership = response.data["memberships"][0]
        self.assertEqual(membership["organization_name"], "Org A")
        self.assertEqual(membership["role"], "branch_manager")
        self.assertEqual(membership["branches"][0]["name"], "Delhi")

    def test_me_never_shows_another_users_memberships(self):
        Membership.objects.create(user=self.other, organization=self.org_b)

        self._authenticate(self.user)
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["memberships"], [])

    def test_me_hides_suspended_memberships(self):
        Membership.objects.create(
            user=self.user,
            organization=self.org_a,
            status=Membership.Status.SUSPENDED,
        )

        self._authenticate(self.user)
        response = self.client.get(reverse("me"))

        self.assertEqual(response.data["memberships"], [])

    def test_user_in_two_organizations_sees_both_roles(self):
        Membership.objects.create(
            user=self.user, organization=self.org_a, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.user,
            organization=self.org_b,
            role=Membership.Role.ACCOUNTANT,
        )

        self._authenticate(self.user)
        response = self.client.get(reverse("me"))

        roles = {m["organization_slug"]: m["role"] for m in response.data["memberships"]}
        self.assertEqual(roles, {"org-a": "owner", "org-b": "accountant"})