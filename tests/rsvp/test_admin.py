import pytest
from django.contrib import admin
from django.urls import reverse

from apps.invitations.models import InvitationResponse


@pytest.mark.django_db
def test_invitation_response_admin_is_read_only(
    admin_client,
    public_invitation,
    rf,
):
    response = InvitationResponse.objects.create(
        invitation=public_invitation,
        status=InvitationResponse.Status.CONFIRMED,
        guest_names=["João"],
    )
    model_admin = admin.site._registry[InvitationResponse]
    request = rf.get("/admin/invitations/invitationresponse/")

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request, response) is False
    assert model_admin.has_delete_permission(request, response) is False
    assert set(model_admin.get_readonly_fields(request, response)) == {
        "id",
        "invitation",
        "status",
        "guest_names",
        "created_at",
    }
    changelist = admin_client.get(
        reverse("admin:invitations_invitationresponse_changelist")
    )
    assert changelist.status_code == 200
