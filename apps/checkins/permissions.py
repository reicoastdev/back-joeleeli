from rest_framework.exceptions import PermissionDenied

from apps.events.models import EventMembership


def require_event_supervisor(request, event_id):
    user = request.user
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Active supervisor access is required.")
    try:
        return EventMembership.objects.select_related("event").get(
            user=user,
            event_id=event_id,
            role=EventMembership.Role.SUPERVISOR,
            is_active=True,
        )
    except EventMembership.DoesNotExist:
        raise PermissionDenied("Active supervisor access is required.") from None
