from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connections

from apps.invitations.models import Invitation
from apps.invitations.public_links import ensure_public_token


def ensure_token_in_independent_connection(invitation_id, barrier):
    close_old_connections()
    try:
        barrier.wait(timeout=10)
        return ensure_public_token(invitation_id)
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_concurrent_token_issuance_is_safe(invitation):
    barrier = Barrier(3)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                ensure_token_in_independent_connection,
                invitation.pk,
                barrier,
            )
            for _ in range(2)
        ]
        barrier.wait(timeout=10)
        returned_tokens = [future.result(timeout=10) for future in futures]

    invitation.refresh_from_db()

    assert returned_tokens[0] == returned_tokens[1]
    assert invitation.public_token == returned_tokens[0]
    assert invitation.public_token_issued_at is not None
    assert Invitation.objects.exclude(public_token=None).count() == 1
