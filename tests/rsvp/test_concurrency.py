from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connections
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.invitations.models import Invitation, InvitationResponse


def submit_in_independent_connection(*, token, payload, barrier):
    close_old_connections()
    try:
        barrier.wait(timeout=10)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client.put(
            reverse("public-rsvp"),
            payload,
            format="json",
        )
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_concurrent_puts_leave_one_complete_guest_composition(
    public_invitation,
    public_token,
):
    barrier = Barrier(3)
    payloads = [
        {"status": "CONFIRMED", "guests": ["João", "Maria"]},
        {"status": "CONFIRMED", "guests": ["Carlos"]},
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                submit_in_independent_connection,
                token=public_token,
                payload=payload,
                barrier=barrier,
            )
            for payload in payloads
        ]
        barrier.wait(timeout=10)
        responses = [future.result(timeout=10) for future in futures]

    assert [response.status_code for response in responses] == [
        status.HTTP_200_OK,
        status.HTTP_200_OK,
    ]
    public_invitation = Invitation.objects.get(pk=public_invitation.pk)
    final_names = list(
        public_invitation.guests.filter(is_active=True)
        .order_by("pk")
        .values_list("name", flat=True)
    )
    assert final_names in [["João", "Maria"], ["Carlos"]]
    assert InvitationResponse.objects.filter(invitation=public_invitation).count() == 2
    latest_response = InvitationResponse.objects.filter(
        invitation=public_invitation
    ).latest("created_at", "pk")
    assert latest_response.guest_names == final_names
