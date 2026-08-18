import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_openapi_documents_public_rsvp_without_authentication(api_client):
    response = api_client.get(reverse("schema"), HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    schema = response.json()
    path = schema["paths"]["/api/v1/public/invitations/{token}/rsvp/"]
    assert {"get", "put"}.issubset(path)
    assert "security" not in schema
    assert path["get"].get("security", []) == []
    assert path["put"].get("security", []) == []
    assert "404" in path["get"]["responses"]
    assert {"400", "404", "409"}.issubset(path["put"]["responses"])
