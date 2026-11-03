import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

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


class Invitation(models.Model):
    """An invitation for someone to join an organization with a role.

    Only a hash of the secret token is stored. The real token is shown
    once, at creation time, and goes into the invitation link.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="invitations",
    )

    email = models.EmailField()

    role = models.CharField(
        max_length=30,
        choices=Membership.Role.choices,
        default=Membership.Role.CASHIER,
    )

    token_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    expires_at = models.DateTimeField()

    accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memberships_invitation"
        ordering = ["-created_at"]
        constraints = [
            # Only one open invitation per email per organization.
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=Q(status="pending"),
                name="uniq_pending_invite_per_org_email",
            ),
        ]

    def __str__(self):
        return f"Invite {self.email} -> {self.organization.name} ({self.status})"

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def create_with_token(
        cls, *, organization, email, role, invited_by=None, valid_days=7
    ):
        """Create an invitation. Returns (invitation, raw_token)."""
        raw_token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            organization=organization,
            email=email,
            role=role,
            invited_by=invited_by,
            token_hash=cls.hash_token(raw_token),
            expires_at=timezone.now() + timedelta(days=valid_days),
        )
        return invitation, raw_token

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_usable(self):
        return self.status == self.Status.PENDING and not self.is_expired

    def save(self, *args, **kwargs):
        # Emails are compared in lowercase so "A@x.com" and "a@x.com" match.
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)