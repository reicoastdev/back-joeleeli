import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_check():
    response = APIClient().get(reverse("health-check"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
