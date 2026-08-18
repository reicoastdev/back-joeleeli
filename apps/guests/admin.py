from django.contrib import admin

from .models import Guest
from .services import save_guest


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("name", "invitation", "is_active", "created_at")
    list_filter = ("is_active", "invitation__event")
    search_fields = (
        "name",
        "invitation__description",
        "invitation__responsible_name",
    )
    list_select_related = ("invitation", "invitation__event")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj is not None:
            return (*readonly_fields, "invitation")
        return readonly_fields

    def save_model(self, request, obj, form, change):
        save_guest(obj)
