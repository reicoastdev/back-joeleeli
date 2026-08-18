from django.core.exceptions import ValidationError


class InvitationCapacityExceeded(ValidationError):
    """Raised when an invitation composition would exceed its capacity."""
