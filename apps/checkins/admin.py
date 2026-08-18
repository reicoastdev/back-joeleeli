from django.contrib import admin

from .models import CheckIn, CheckInOperation


class AuditReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(CheckIn)
class CheckInAdmin(AuditReadOnlyAdmin):
    list_display = (
        "id",
        "event",
        "guest",
        "checked_in_at",
        "checked_in_by",
        "cancelled_at",
    )
    list_filter = ("event", "checked_in_at", "cancelled_at")
    search_fields = ("guest__name", "checked_in_by__email")
    list_select_related = ("event", "guest", "checked_in_by", "cancelled_by")


@admin.register(CheckInOperation)
class CheckInOperationAdmin(AuditReadOnlyAdmin):
    list_display = ("id", "event", "user", "action", "response_status", "created_at")
    list_filter = ("event", "action", "response_status")
    search_fields = ("user__email", "idempotency_key")
    list_select_related = ("event", "user")
