from django.contrib import admin

from .models import BranchAssignment, Invitation, Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "status", "created_at")
    list_filter = ("role", "status", "organization")
    search_fields = ("user__email", "organization__name")
    list_select_related = ("user", "organization")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BranchAssignment)
class BranchAssignmentAdmin(admin.ModelAdmin):
    list_display = ("membership", "branch", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = ("membership__user__email", "branch__name")
    list_select_related = ("membership__user", "branch", "organization")
    readonly_fields = ("id", "organization", "created_at")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "role",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "role", "organization")
    search_fields = ("email", "organization__name")
    list_select_related = ("organization",)
    readonly_fields = (
        "id",
        "token_hash",
        "accepted_at",
        "created_at",
    )

    # Invitations must be created through code, because only the code
    # can produce and hand out the secret token. So no "Add" button.
    def has_add_permission(self, request):
        return False