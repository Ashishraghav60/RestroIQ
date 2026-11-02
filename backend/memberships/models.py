import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from organizations.models import Branch, Organization


class Membership(models.Model):
    """Links one user to one organization, with a role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Organization Owner"
        ADMIN = "admin", "Organization Admin"
        BRAND_MANAGER = "brand_manager", "Brand Manager"
        REGIONAL_MANAGER = "regional_manager", "Regional Manager"
        BRANCH_MANAGER = "branch_manager", "Branch Manager"
        ACCOUNTANT = "accountant", "Accountant"
        INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"
        HR_MANAGER = "hr_manager", "HR Manager"
        CASHIER = "cashier", "Cashier"
        KITCHEN_STAFF = "kitchen_staff", "Kitchen Staff"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.CASHIER,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "memberships_membership"
        ordering = ["organization__name", "user__email"]
        constraints = [
            # A user has at most one membership per organization.
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="uniq_membership_user_org",
            ),
            # Needed later for tenant-safe composite foreign keys (M6).
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="uniq_membership_id_org",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.organization.name} ({self.role})"


class BranchAssignment(models.Model):
    """Says which branches a membership works at."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    membership = models.ForeignKey(
        Membership,
        on_delete=models.CASCADE,
        related_name="branch_assignments",
    )

    # Copied from the membership so the row carries its own tenant column.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="branch_assignments",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="assignments",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memberships_branchassignment"
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "branch"],
                name="uniq_assignment_membership_branch",
            ),
        ]

    def __str__(self):
        return f"{self.membership.user} @ {self.branch.name}"

    def _check_hierarchy(self):
        if not (self.membership_id and self.branch_id):
            return
        org_id = self.membership.organization_id
        if self.branch.organization_id != org_id:
            raise ValidationError(
                "The branch belongs to a different organization."
            )
        if self.organization_id and self.organization_id != org_id:
            raise ValidationError(
                "The organization does not match the membership."
            )

    def clean(self):
        super().clean()
        self._check_hierarchy()

    def save(self, *args, **kwargs):
        if self.organization_id is None and self.membership_id:
            self.organization_id = self.membership.organization_id
        self._check_hierarchy()
        super().save(*args, **kwargs)