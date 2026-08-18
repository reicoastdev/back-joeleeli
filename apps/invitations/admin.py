from django.contrib import admin

from apps.guests.services import update_guest_limit

from .models import Invitation


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
