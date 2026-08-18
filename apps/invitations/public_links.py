import secrets

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Invitation

TOKEN_GENERATION_ATTEMPTS = 3


class PublicInvitationNotFound(ObjectDoesNotExist):
    """Raised when a public invitation credential cannot be resolved."""


class PublicTokenGenerationError(RuntimeError):
    """Raised when a unique public credential cannot be generated."""


def _not_found_error():
    return PublicInvitationNotFound("Public invitation credential was not found.")


def _issue_new_token(invitation):
    previous_token = invitation.public_token
    for _attempt in range(TOKEN_GENERATION_ATTEMPTS):
        candidate_token = secrets.token_urlsafe(32)
        if candidate_token == previous_token:
            continue

        invitation.public_token = candidate_token
        invitation.public_token_issued_at = timezone.now()
        try:
            with transaction.atomic():
                invitation.save(
                    update_fields=[
                        "public_token",
                        "public_token_issued_at",
                        "updated_at",
                    ]
                )
        except IntegrityError:
            continue
        return invitation.public_token

    raise PublicTokenGenerationError(
        "Unable to generate a unique public invitation credential."
    )


@transaction.atomic
def ensure_public_token(invitation_id):
    invitation = Invitation.objects.select_for_update().get(pk=invitation_id)
    if invitation.public_token is not None:
        return invitation.public_token
    return _issue_new_token(invitation)


@transaction.atomic
def rotate_public_token(invitation_id):
    invitation = Invitation.objects.select_for_update().get(pk=invitation_id)
    return _issue_new_token(invitation)


@transaction.atomic
def revoke_public_token(invitation_id):
    invitation = Invitation.objects.select_for_update().get(pk=invitation_id)
    invitation.public_token = None
    invitation.public_token_issued_at = None
    invitation.save(
        update_fields=["public_token", "public_token_issued_at", "updated_at"]
    )


def resolve_public_token(token):
    if not token:
        raise _not_found_error()

    try:
        return Invitation.objects.get(public_token=token)
    except Invitation.DoesNotExist:
        raise _not_found_error() from None
