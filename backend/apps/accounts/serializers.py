from rest_framework import serializers

from apps.accounts.models import DeletionRequest, User
from apps.accounts.services import normalize_uz_phone, validate_user_password


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value):
        return normalize_uz_phone(value)


class ShopRegistrationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.RegexField(r"^\d{6}$")
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        error_messages={"min_length": "Parol kamida 8 ta belgidan iborat bo‘lsin."},
    )

    def validate_phone(self, value):
        return normalize_uz_phone(value)

    def validate_password(self, value):
        validate_user_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_phone(self, value):
        return normalize_uz_phone(value)


class LoginOTPVerifySerializer(LoginSerializer):
    code = serializers.RegexField(r"^\d{6}$", write_only=True)


class PasswordResetSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.RegexField(r"^\d{6}$")
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        error_messages={"min_length": "Parol kamida 8 ta belgidan iborat bo‘lsin."},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        error_messages={"min_length": "Parol kamida 8 ta belgidan iborat bo‘lsin."},
    )

    def validate_phone(self, value):
        return normalize_uz_phone(value)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Parollar bir-biriga mos kelmadi."}
            )
        validate_user_password(attrs["password"])
        return attrs


class PhoneChangeRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value):
        phone = normalize_uz_phone(value)
        request = self.context["request"]
        if phone == request.user.phone:
            raise serializers.ValidationError("Yangi telefon raqami hozirgi raqamdan farq qilishi kerak.")
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")
        return phone


class PhoneChangeSerializer(PhoneChangeRequestSerializer):
    code = serializers.RegexField(r"^\d{6}$")


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        error_messages={"min_length": "Parol kamida 8 ta belgidan iborat bo‘lsin."},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        error_messages={"min_length": "Parol kamida 8 ta belgidan iborat bo‘lsin."},
    )

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Joriy parol noto‘g‘ri."}
            )
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Parollar bir-biriga mos kelmadi."}
            )
        validate_user_password(attrs["password"], user=user)
        return attrs


class UserSummarySerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ("id", "phone", "role", "company_id", "must_change_password")


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = UserSummarySerializer()


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RegistrationResponseSerializer(DetailResponseSerializer):
    user = UserSummarySerializer()


class RefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class CSRFTokenResponseSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class CurrentUserResponseSerializer(UserSummarySerializer):
    is_active = serializers.BooleanField()
    shops = serializers.ListField(child=serializers.DictField())

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + ("is_active", "shops")


class DeletionPendingResponseSerializer(serializers.Serializer):
    pending = serializers.BooleanField()
    requested_at = serializers.DateTimeField(required=False)
    scheduled_for = serializers.DateTimeField(required=False)
    reason = serializers.CharField(required=False)


class DeletionAcceptedResponseSerializer(DetailResponseSerializer):
    scheduled_for = serializers.DateTimeField()


class DeletionRequestSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=DeletionRequest.Reason.choices)
    reason_other = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    code = serializers.RegexField(r"^\d{6}$")


class AccountRestoreSerializer(LoginOTPVerifySerializer):
    pass
