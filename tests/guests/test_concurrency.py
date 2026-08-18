from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connections

from apps.guests.exceptions import InvitationCapacityExceeded
from apps.guests.models import Guest
from apps.guests.services import add_guest, update_guest_limit


def run_concurrent_operation(barrier, operation):
    close_old_connections()
    try:
        barrier.wait(timeout=10)
        operation()
    except InvitationCapacityExceeded:
        return "capacity_exceeded"
    else:
        return "success"
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_concurrent_guest_additions_are_serialized(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=2)
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    barrier = Barrier(3)

    operations = (
        lambda: add_guest(invitation_id=invitation.pk, name="Maria Oliveira"),
        lambda: add_guest(invitation_id=invitation.pk, name="Ana Oliveira"),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(run_concurrent_operation, barrier, operation)
            for operation in operations
        ]
        barrier.wait(timeout=10)
        results = [future.result(timeout=10) for future in futures]

    assert results.count("success") == 1
    assert results.count("capacity_exceeded") == 1
    assert Guest.objects.filter(invitation=invitation, is_active=True).count() == 2


@pytest.mark.django_db(transaction=True)
def test_guest_addition_and_limit_reduction_use_same_lock(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=2)
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    barrier = Barrier(3)

    operations = (
        lambda: add_guest(invitation_id=invitation.pk, name="Maria Oliveira"),
        lambda: update_guest_limit(invitation_id=invitation.pk, guest_limit=1),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(run_concurrent_operation, barrier, operation)
            for operation in operations
        ]
        barrier.wait(timeout=10)
        results = [future.result(timeout=10) for future in futures]

    invitation.refresh_from_db()
    active_guest_count = Guest.objects.filter(
        invitation=invitation,
        is_active=True,
    ).count()
    assert results.count("success") == 1
    assert results.count("capacity_exceeded") == 1
    assert active_guest_count <= invitation.guest_limit
