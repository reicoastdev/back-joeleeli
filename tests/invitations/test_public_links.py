from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.invitations.admin import InvitationAdmin
from apps.invitations.models import Invitation
from apps.invitations.public_links import (
    PublicInvitationNotFound,
    PublicTokenGenerationError,
    ensure_public_token,
    resolve_public_token,
    revoke_public_token,
    rotate_public_token,
)


def create_invitation(invitation_values, **overrides):
    values = invitation_values | overrides
    return Invitation.objects.create(**values)


def test_invitation_starts_without_public_token(invitation):
    assert invitation.public_token is None
    assert invitation.public_token_issued_at is None


def test_ensure_public_token_generates_and_persists_credential(invitation):
    token = ensure_public_token(invitation.pk)
    invitation.refresh_from_db()

    assert len(token) >= 32
    assert invitation.public_token == token
    assert invitation.public_token_issued_at is not None
    assert timezone.is_aware(invitation.public_token_issued_at)


def test_ensure_public_token_returns_existing_credential(invitation):
    token = ensure_public_token(invitation.pk)
    invitation.refresh_from_db()
    issued_at = invitation.public_token_issued_at

    same_token = ensure_public_token(invitation.pk)
    invitation.refresh_from_db()

    assert same_token == token
    assert invitation.public_token_issued_at == issued_at


def test_different_invitations_receive_different_tokens(
    invitation,
    invitation_values,
):
    other_invitation = create_invitation(
        invitation_values,
        description="Família Santos",
    )

    assert ensure_public_token(invitation.pk) != ensure_public_token(
        other_invitation.pk
    )


def test_public_token_is_unique_in_database(invitation, invitation_values):
    token = ensure_public_token(invitation.pk)
    other_invitation = create_invitation(
        invitation_values,
        description="Família Santos",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.filter(pk=other_invitation.pk).update(
            public_token=token,
            public_token_issued_at=timezone.now(),
        )


def test_token_generation_retries_database_collision(
    invitation,
    invitation_values,
):
    existing_token = ensure_public_token(invitation.pk)
    other_invitation = create_invitation(
        invitation_values,
        description="Família Santos",
    )
    replacement_token = "replacement-token-with-enough-entropy-123456789"

    with patch(
        "apps.invitations.public_links.secrets.token_urlsafe",
        side_effect=[existing_token, replacement_token],
    ):
        issued_token = ensure_public_token(other_invitation.pk)

    assert issued_token == replacement_token
    other_invitation.refresh_from_db()
    assert other_invitation.public_token == replacement_token


def test_token_generation_stops_after_limited_collisions(
    invitation,
    invitation_values,
):
    existing_token = ensure_public_token(invitation.pk)
    other_invitation = create_invitation(
        invitation_values,
        description="Família Santos",
    )

    with (
        patch(
            "apps.invitations.public_links.secrets.token_urlsafe",
            return_value=existing_token,
        ),
        pytest.raises(PublicTokenGenerationError) as exc_info,
    ):
        ensure_public_token(other_invitation.pk)

    assert existing_token not in str(exc_info.value)
    other_invitation.refresh_from_db()
    assert other_invitation.public_token is None
    assert other_invitation.public_token_issued_at is None


def test_rotate_replaces_token_and_invalidates_previous_one(invitation):
    old_token = ensure_public_token(invitation.pk)

    new_token = rotate_public_token(invitation.pk)

    assert new_token != old_token
    with pytest.raises(PublicInvitationNotFound):
        resolve_public_token(old_token)
    assert resolve_public_token(new_token) == invitation


def test_rotate_retries_if_generator_returns_current_token(invitation):
    old_token = ensure_public_token(invitation.pk)
    replacement_token = "replacement-token-with-enough-entropy-123456789"

    with patch(
        "apps.invitations.public_links.secrets.token_urlsafe",
        side_effect=[old_token, replacement_token],
    ):
        new_token = rotate_public_token(invitation.pk)

    assert new_token == replacement_token


def test_revoke_clears_credential_and_prevents_resolution(invitation):
    token = ensure_public_token(invitation.pk)

    revoke_public_token(invitation.pk)
    invitation.refresh_from_db()

    assert invitation.public_token is None
    assert invitation.public_token_issued_at is None
    with pytest.raises(PublicInvitationNotFound):
        resolve_public_token(token)


def test_ensure_after_revoke_issues_new_credential(invitation):
    old_token = ensure_public_token(invitation.pk)
    revoke_public_token(invitation.pk)

    new_token = ensure_public_token(invitation.pk)

    assert new_token != old_token


def test_public_token_resolution_is_exact_and_case_sensitive(invitation):
    token = "KnownCaseSensitiveToken_123456789abcdefghijk"
    with patch(
        "apps.invitations.public_links.secrets.token_urlsafe",
        return_value=token,
    ):
        ensure_public_token(invitation.pk)

    assert resolve_public_token(token) == invitation
    with pytest.raises(PublicInvitationNotFound):
        resolve_public_token(token.swapcase())
    with pytest.raises(PublicInvitationNotFound):
        resolve_public_token(token[:-1])


@pytest.mark.parametrize("token", [None, ""])
def test_missing_public_token_raises_generic_error(token):
    with pytest.raises(PublicInvitationNotFound) as exc_info:
        resolve_public_token(token)

    assert str(exc_info.value) == "Public invitation credential was not found."


def test_unknown_token_is_not_exposed_in_exception(db):
    unknown_token = "SUPER_SECRET_PUBLIC_TOKEN_XYZ"

    with pytest.raises(PublicInvitationNotFound) as exc_info:
        resolve_public_token(unknown_token)

    assert unknown_token not in str(exc_info.value)


def test_empty_public_token_is_rejected_by_validation(invitation):
    invitation.public_token = ""
    invitation.public_token_issued_at = timezone.now()

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "public_token" in exc_info.value.message_dict


def test_empty_public_token_is_rejected_by_database(invitation):
    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.filter(pk=invitation.pk).update(
            public_token="",
            public_token_issued_at=timezone.now(),
        )


@pytest.mark.parametrize(
    ("public_token", "issued_at"),
    [
        ("valid-token-with-enough-entropy-123456789", None),
        (None, timezone.now()),
    ],
)
def test_token_and_issued_at_must_change_together_in_database(
    invitation,
    public_token,
    issued_at,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.filter(pk=invitation.pk).update(
            public_token=public_token,
            public_token_issued_at=issued_at,
        )


def test_string_representation_does_not_contain_public_token(invitation):
    token = ensure_public_token(invitation.pk)
    invitation.refresh_from_db()

    assert token not in str(invitation)
    assert str(invitation) == invitation.description


def test_admin_does_not_display_or_allow_editing_public_token(rf):
    model_admin = InvitationAdmin(Invitation, AdminSite())
    request = rf.get("/admin/invitations/invitation/add/")

    assert "public_token" not in model_admin.get_list_display(request)
    assert "public_token_issued_at" not in model_admin.get_list_display(request)
    form = model_admin.get_form(request)
    assert "public_token" not in form.base_fields
    assert "public_token_issued_at" not in form.base_fields
