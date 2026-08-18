from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(email=""),
                name="accounts_user_email_not_empty",
            ),
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_case_insensitive_unique",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = type(self).objects.normalize_email(self.email).lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
