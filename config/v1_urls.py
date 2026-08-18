from django.urls import path

from apps.checkins.views import (
    CancelCheckInView,
    GuestCheckInView,
    InvitationCheckInView,
    LoginView,
    MetricsView,
    SearchView,
)
from apps.health.views import HealthCheckView
from apps.invitations.views import PublicRSVPView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("auth/login/", LoginView.as_view(), name="supervisor-login"),
    path(
        "events/<int:event_id>/check-in/search/",
        SearchView.as_view(),
        name="check-in-search",
    ),
    path(
        "events/<int:event_id>/check-in/metrics/",
        MetricsView.as_view(),
        name="check-in-metrics",
    ),
    path(
        "events/<int:event_id>/check-in/invitations/<int:invitation_id>/",
        InvitationCheckInView.as_view(),
        name="check-in-invitation-detail",
    ),
    path(
        "events/<int:event_id>/check-in/guests/<int:guest_id>/",
        GuestCheckInView.as_view(),
        name="check-in-guest",
    ),
    path(
        "events/<int:event_id>/check-in/check-ins/<int:check_in_id>/cancel/",
        CancelCheckInView.as_view(),
        name="check-in-cancel",
    ),
    path(
        "public/rsvp/",
        PublicRSVPView.as_view(),
        name="public-rsvp",
    ),
]
