from django.urls import path

from apps.health.views import HealthCheckView
from apps.invitations.views import PublicRSVPView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path(
        "public/rsvp/",
        PublicRSVPView.as_view(),
        name="public-rsvp",
    ),
]
