import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Organization(models.Model):

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=255)

    slug = models.SlugField(
        max_length=150,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
    )

    default_currency = models.CharField(
        max_length=3,
        default="INR",
    )

    timezone = models.CharField(
        max_length=50,
        default="Asia/Kolkata",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations_organization"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="brands",
    )

    name = models.CharField(max_length=255)

    slug = models.SlugField(max_length=150)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations_brand"
        ordering = ["name"]
        constraints = [
            # Two organizations may both have a "burger-house" brand,
            # but one organization cannot have it twice.
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="uniq_brand_slug_per_org",
            ),
            # Needed later for tenant-safe composite foreign keys (M6).
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="uniq_brand_id_org",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Region(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Stored on every tenant-owned row so we can filter and
    # protect data by organization without extra joins.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="regions",
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="regions",
    )

    name = models.CharField(max_length=255)

    slug = models.SlugField(max_length=150)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations_region"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "slug"],
                name="uniq_region_slug_per_brand",
            ),
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="uniq_region_id_org",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.brand.name}"

    def _check_hierarchy(self):
        if self.brand_id and self.organization_id:
            if self.brand.organization_id != self.organization_id:
                raise ValidationError(
                    "The brand belongs to a different organization."
                )

    def clean(self):
        super().clean()
        self._check_hierarchy()

    def save(self, *args, **kwargs):
        if self.organization_id is None and self.brand_id:
            self.organization_id = self.brand.organization_id
        self._check_hierarchy()
        super().save(*args, **kwargs)


class Branch(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="branches",
    )

    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="branches",
    )

    name = models.CharField(max_length=255)

    slug = models.SlugField(max_length=150)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Leave blank to use the organization's timezone.
    timezone = models.CharField(
        max_length=50,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations_branch"
        ordering = ["name"]
        verbose_name_plural = "branches"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="uniq_branch_slug_per_org",
            ),
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="uniq_branch_id_org",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.region.name}"

    @property
    def brand(self):
        return self.region.brand

    @property
    def effective_timezone(self):
        return self.timezone or self.organization.timezone

    def _check_hierarchy(self):
        if self.region_id and self.organization_id:
            if self.region.organization_id != self.organization_id:
                raise ValidationError(
                    "The region belongs to a different organization."
                )

    def clean(self):
        super().clean()
        self._check_hierarchy()

    def save(self, *args, **kwargs):
        if self.organization_id is None and self.region_id:
            self.organization_id = self.region.organization_id
        self._check_hierarchy()
        super().save(*args, **kwargs)