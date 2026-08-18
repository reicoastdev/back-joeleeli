import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.checkins.models import CheckIn


@pytest.mark.django_db
def test_check_in_admin_is_read_only_and_disables_delete(supervisor):
    supervisor.is_staff = True
    supervisor.save(update_fields=("is_staff",))
    request = RequestFactory().get("/admin/checkins/checkin/")
    request.user = supervisor
    model_admin = admin.site._registry[CheckIn]

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
    assert set(model_admin.get_readonly_fields(request)) == {
        field.name for field in CheckIn._meta.fields
    }
