from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .public_links import PublicInvitationNotFound
from .public_rsvp import RSVPClosedError, get_public_rsvp, submit_public_rsvp
from .serializers import (
    PublicNotFoundSerializer,
    PublicRSVPResponseSerializer,
    PublicRSVPSubmissionSerializer,
    RSVPClosedSerializer,
)


def _generic_not_found():
    return NotFound("Public invitation was not found.")


class PublicRSVPView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(
        operation_id="public_rsvp_retrieve",
        description="Retrieve the current public RSVP state for an invitation.",
        responses={
            status.HTTP_200_OK: PublicRSVPResponseSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=PublicNotFoundSerializer,
                description="Public invitation unavailable.",
            ),
        },
        auth=[],
    )
    def get(self, request, token):
        try:
            response_data = get_public_rsvp(token)
        except PublicInvitationNotFound:
            raise _generic_not_found() from None
        return Response(response_data)

    @extend_schema(
        operation_id="public_rsvp_update",
        description=("Submit a complete RSVP composition using CONFIRMED or DECLINED."),
        request=PublicRSVPSubmissionSerializer,
        responses={
            status.HTTP_200_OK: PublicRSVPResponseSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid RSVP payload."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=PublicNotFoundSerializer,
                description="Public invitation unavailable.",
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                response=RSVPClosedSerializer,
                description="The RSVP deadline has passed.",
            ),
        },
        auth=[],
    )
    def put(self, request, token):
        try:
            response_data = submit_public_rsvp(token=token, payload=request.data)
        except PublicInvitationNotFound:
            raise _generic_not_found() from None
        except RSVPClosedError:
            return Response(
                {"code": "rsvp_closed"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(response_data)
