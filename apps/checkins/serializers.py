from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class GroupCheckInSerializer(serializers.Serializer):
    guest_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_guest_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Guest IDs must be unique.")
        return value


class CancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
