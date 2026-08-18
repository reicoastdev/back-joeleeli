import pytest
from django.contrib.admin.sites import AdminSite

from apps.guests.admin import GuestAdmin
from apps.guests.exceptions import InvitationCapacityExceeded
from apps.guests.models import Guest
from apps.guests.services import add_guest, update_guest_limit
from apps.invitations.admin import InvitationAdmin
from apps.invitations.models import Invitation


def test_guest_admin_creation_uses_capacity_guard(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=1)
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    guest = Guest(invitation=invitation, name="Maria Oliveira")
    guest_admin = GuestAdmin(Guest, AdminSite())

    with pytest.raises(InvitationCapacityExceeded):
        guest_admin.save_model(request=None, obj=guest, form=None, change=False)


def test_guest_admin_reactivation_uses_capacity_guard(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=1)
    inactive_guest = add_guest(
        invitation_id=invitation.pk,
        name="Pedro Oliveira",
        is_active=False,
    )
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    inactive_guest.is_active = True
    guest_admin = GuestAdmin(Guest, AdminSite())

    with pytest.raises(InvitationCapacityExceeded):
        guest_admin.save_model(
            request=None,
            obj=inactive_guest,
            form=None,
            change=True,
        )


def test_invitation_admin_limit_update_uses_capacity_guard(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    add_guest(invitation_id=invitation.pk, name="Maria Oliveira")
    invitation.guest_limit = 1
    invitation_admin = InvitationAdmin(Invitation, AdminSite())
    form = type("ChangedGuestLimitForm", (), {"changed_data": ["guest_limit"]})()

    with pytest.raises(InvitationCapacityExceeded):
        invitation_admin.save_model(
            request=None,
            obj=invitation,
            form=form,
            change=True,
        )
