from django.contrib import admin

from .models import Branch, Brand, Organization, Region


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "status",
        "default_currency",
        "timezone",
        "created_at",
    )

    list_filter = (
        "status",
        "default_currency",
    )

    search_fields = (
        "name",
        "slug",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "organization",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "organization",
    )

    search_fields = (
        "name",
        "slug",
        "organization__name",
    )

    list_select_related = ("organization",)

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "brand",
        "organization",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "organization",
        "brand",
    )

    search_fields = (
        "name",
        "slug",
        "brand__name",
        "organization__name",
    )

    list_select_related = ("brand", "organization")

    # The organization is filled in automatically from the brand,
    # so nobody can pick a mismatched one by mistake.
    readonly_fields = (
        "id",
        "organization",
        "created_at",
        "updated_at",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "region",
        "get_brand",
        "organization",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "organization",
    )

    search_fields = (
        "name",
        "slug",
        "region__name",
        "organization__name",
    )

    list_select_related = ("region__brand", "organization")

    # The organization is filled in automatically from the region.
    readonly_fields = (
        "id",
        "organization",
        "created_at",
        "updated_at",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    @admin.display(description="Brand")
    def get_brand(self, obj):
        return obj.region.brand.name