from django.contrib import admin

from apps.guests.services import update_guest_limit

from .models import Invitation, InvitationResponse


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "responsible_name",
        "event",
        "category",
        "guest_limit",
        "is_active",
    )
    list_filter = ("event", "category", "is_active")
    search_fields = ("description", "responsible_name", "responsible_phone")
    list_select_related = ("event", "category")

    def save_model(self, request, obj, form, change):
        if change and "guest_limit" in form.changed_data:
            update_guest_limit(
                invitation_id=obj.pk,
                guest_limit=obj.guest_limit,
            )
        super().save_model(request, obj, form, change)


@admin.register(InvitationResponse)
class InvitationResponseAdmin(admin.ModelAdmin):
    list_display = ("invitation", "status", "created_at")
    list_filter = ("status", "invitation__event")
    search_fields = (
        "invitation__description",
        "invitation__responsible_name",
    )
    list_select_related = ("invitation", "invitation__event")
    readonly_fields = ("id", "invitation", "status", "guest_names", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
