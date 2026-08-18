from django.contrib import admin

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
