
from django.contrib import admin

from .models import Organization


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
