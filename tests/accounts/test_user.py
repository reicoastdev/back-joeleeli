import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user_with_email():
    user = User.objects.create_user(
        email="Guest@Example.com",
        password="strong-test-password",
    )

    assert user.email == "guest@example.com"
    assert user.check_password("strong-test-password")
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_create_user_requires_email():
    with pytest.raises(ValueError, match="email address is required"):
        User.objects.create_user(email="", password="strong-test-password")


@pytest.mark.django_db(transaction=True)
def test_user_email_is_unique_case_insensitively():
    User.objects.create_user(
        email="guest@example.com",
        password="strong-test-password",
    )

    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email="GUEST@example.com",
            password="another-strong-password",
        )


@pytest.mark.django_db
def test_create_superuser():
    user = User.objects.create_superuser(
        email="admin@example.com",
        password="strong-test-password",
    )

    assert user.is_active is True
    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_email_authentication_lookup_is_case_insensitive():
    user = User.objects.create_user(
        email="guest@example.com",
        password="strong-test-password",
    )

    assert User.objects.get_by_natural_key("GUEST@EXAMPLE.COM") == user
