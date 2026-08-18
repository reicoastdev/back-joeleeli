from django.contrib import admin

from .models import Event, InvitationCategory


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "starts_at", "rsvp_deadline", "status")
    list_filter = ("status",)
    search_fields = ("name", "location")


@admin.register(InvitationCategory)
class InvitationCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "is_active")
    list_filter = ("is_active", "event")
    search_fields = ("name", "event__name")
    list_select_related = ("event",)
