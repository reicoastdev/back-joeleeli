from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken

from apps.events.models import EventMembership

from .idempotency import execute_idempotent
from .models import CheckInOperation
from .permissions import require_event_supervisor
from .serializers import CancellationSerializer, GroupCheckInSerializer, LoginSerializer
from .services import (
    OperationError,
    cancel_check_in,
    check_in_guest,
    check_in_guests,
    event_metrics,
    invitation_detail,
    search_invitations,
)


def _operation_response(callback):
    try:
        return callback()
    except OperationError as error:
        return error.payload, error.status_code


def _validation_response(serializer):
    if serializer.is_valid():
        return None
    return {"code": "invalid_request", "errors": serializer.errors}, 400


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access = AccessToken.for_user(user)
        memberships = (
            EventMembership.objects.filter(user=user, is_active=True)
            .select_related("event")
            .order_by("event__starts_at", "event_id")
        )
        return Response(
            {
                "access_token": str(access),
                "expires_in": int(access["exp"] - access.current_time.timestamp()),
                "user": {"id": user.pk, "email": user.email},
                "events": [
                    {
                        "id": membership.event_id,
                        "name": membership.event.name,
                        "role": membership.role,
                    }
                    for membership in memberships
                ],
            }
        )


class EventOperationalView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_membership(self, request, event_id):
        return require_event_supervisor(request, event_id)


class SearchView(EventOperationalView):
    def get(self, request, event_id):
        self.get_membership(request, event_id)
        return Response(
            {
                "results": search_invitations(
                    event_id=event_id,
                    query=request.GET.get("q", ""),
                )
            }
        )


class MetricsView(EventOperationalView):
    def get(self, request, event_id):
        self.get_membership(request, event_id)
        return Response(event_metrics(event_id=event_id))


class IdempotentMutationView(EventOperationalView):
    action = None

    def execute(self, request, event_id, request_data, callback):
        membership = self.get_membership(request, event_id)
        payload, response_status, replayed = execute_idempotent(
            event=membership.event,
            user=request.user,
            raw_key=request.headers.get("Idempotency-Key"),
            action=self.action,
            request_data=request_data,
            operation=lambda: _operation_response(callback),
        )
        response = Response(payload, status=response_status)
        if replayed:
            response["Idempotency-Replayed"] = "true"
        return response


class GuestCheckInView(IdempotentMutationView):
    action = CheckInOperation.Action.INDIVIDUAL

    def post(self, request, event_id, guest_id):
        return self.execute(
            request,
            event_id,
            {"guest_id": guest_id, "body": request.data},
            lambda: check_in_guest(
                event_id=event_id,
                guest_id=guest_id,
                user=request.user,
            ),
        )


class InvitationCheckInView(IdempotentMutationView):
    action = CheckInOperation.Action.GROUP

    def get(self, request, event_id, invitation_id):
        self.get_membership(request, event_id)
        try:
            payload = invitation_detail(
                event_id=event_id,
                invitation_id=invitation_id,
            )
        except OperationError as error:
            return Response(error.payload, status=error.status_code)
        return Response(payload)

    def post(self, request, event_id, invitation_id):
        def operation():
            serializer = GroupCheckInSerializer(data=request.data)
            invalid = _validation_response(serializer)
            if invalid:
                return invalid
            return check_in_guests(
                event_id=event_id,
                invitation_id=invitation_id,
                guest_ids=serializer.validated_data["guest_ids"],
                user=request.user,
            )

        return self.execute(
            request,
            event_id,
            {"invitation_id": invitation_id, "body": request.data},
            operation,
        )


class CancelCheckInView(IdempotentMutationView):
    action = CheckInOperation.Action.CANCEL

    def post(self, request, event_id, check_in_id):
        def operation():
            serializer = CancellationSerializer(data=request.data)
            invalid = _validation_response(serializer)
            if invalid:
                return invalid
            return cancel_check_in(
                event_id=event_id,
                check_in_id=check_in_id,
                reason=serializer.validated_data["reason"],
                user=request.user,
            )

        return self.execute(
            request,
            event_id,
            {"check_in_id": check_in_id, "body": request.data},
            operation,
        )
