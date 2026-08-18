from rest_framework import serializers


class GuestNameField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class PublicRSVPSubmissionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["CONFIRMED", "DECLINED"])
    guests = serializers.ListField(
        child=GuestNameField(max_length=255, allow_blank=False, trim_whitespace=True),
        required=False,
        default=list,
    )

    def validate(self, attrs):
        status = attrs["status"]
        guest_names = attrs["guests"]

        if status == "CONFIRMED" and not guest_names:
            raise serializers.ValidationError(
                {"guests": "At least one guest is required when confirming."}
            )
        if status == "DECLINED" and guest_names:
            raise serializers.ValidationError(
                {"guests": "Guests must be empty when declining."}
            )
        return attrs


class PublicEventSerializer(serializers.Serializer):
    name = serializers.CharField()
    starts_at = serializers.DateTimeField()
    timezone = serializers.CharField()
    location = serializers.CharField()
    rsvp_deadline = serializers.DateTimeField()


class PublicInvitationSerializer(serializers.Serializer):
    description = serializers.CharField()
    responsible_name = serializers.CharField()
    guest_limit = serializers.IntegerField()


class PublicRSVPStateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["PENDING", "CONFIRMED", "DECLINED"])
    guests = serializers.ListField(child=serializers.CharField())
    can_respond = serializers.BooleanField()


class PublicRSVPResponseSerializer(serializers.Serializer):
    event = PublicEventSerializer()
    invitation = PublicInvitationSerializer()
    rsvp = PublicRSVPStateSerializer()


class PublicNotFoundSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RSVPClosedSerializer(serializers.Serializer):
    code = serializers.CharField()
