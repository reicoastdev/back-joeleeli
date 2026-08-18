from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections, connections
from rest_framework.test import APIClient

from apps.checkins.models import CheckIn, CheckInOperation


def _concurrent_check_in(barrier, token, url, key):
    close_old_connections()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    try:
        barrier.wait(timeout=10)
        response = client.post(
            url,
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        return response.status_code, response.json()["result"]
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_concurrent_check_ins_create_only_one_active_record(
    authenticated_client, event, guests
):
    token = authenticated_client._credentials["HTTP_AUTHORIZATION"].split()[1]
    url = f"/api/v1/events/{event.pk}/check-in/guests/{guests[0].pk}/"
    barrier = Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _concurrent_check_in,
                barrier,
                token,
                url,
                str(uuid4()),
            )
            for _ in range(2)
        ]
        barrier.wait(timeout=10)
        results = [future.result(timeout=10) for future in futures]

    assert sorted(results) == [(200, "ALREADY_PRESENT"), (201, "CHECKED_IN")]
    assert (
        CheckIn.objects.filter(guest=guests[0], cancelled_at__isnull=True).count() == 1
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_idempotency_key_replays_single_operation(
    authenticated_client, event, guests
):
    token = authenticated_client._credentials["HTTP_AUTHORIZATION"].split()[1]
    url = f"/api/v1/events/{event.pk}/check-in/guests/{guests[0].pk}/"
    key = str(uuid4())
    barrier = Barrier(3)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_concurrent_check_in, barrier, token, url, key)
            for _ in range(2)
        ]
        barrier.wait(timeout=10)
        results = [future.result(timeout=10) for future in futures]

    assert results == [(201, "CHECKED_IN"), (201, "CHECKED_IN")]
    assert (
        CheckIn.objects.filter(guest=guests[0], cancelled_at__isnull=True).count() == 1
    )
    assert CheckInOperation.objects.filter(idempotency_key=key).count() == 1
