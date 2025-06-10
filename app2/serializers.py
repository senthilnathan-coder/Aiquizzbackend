from rest_framework_mongoengine.serializers import DocumentSerializer
from app.serializers import *
from app2.models import *
from app.models import *
from rest_framework import serializers
from email_validator import validate_email as email_validator_func, EmailNotValidError

class UserSerializer(DocumentSerializer):
    """
    Serializer for creating a new User (signup).
    FIXED: Ensures 'password_hash' is present before model instantiation.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'full_name', 'phone_number', 'email', 'password', 'confirm_password']
        read_only_fields = ['id', 'is_active', 'is_verified', 'created_at', 'last_login', 'last_quiz_created_at']

    def validate(self, data):
        # Already doing this validation, which is good.
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data
    
    def validate_phone_number(self, value):
        cleaned_phone_number = ''.join(filter(str.isdigit, value))
        if not (len(cleaned_phone_number) == 10 and cleaned_phone_number.isdigit() and cleaned_phone_number[0] in '6789'):
            raise serializers.ValidationError("Phone number must be 10 digits and start with 6, 7, 8, or 9.")
        return cleaned_phone_number

    def validate_email(self, value):
        try:
            email_validator_func(value)
        except EmailNotValidError:
            raise serializers.ValidationError("Invalid email address format.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        # We need confirm_password for validation here too, though it's already done in validate()
        confirm_password = validated_data.pop('confirm_password') 

        # --- THE FIX IS HERE ---
        # 1. Generate the password hash first.
        # 2. Add it to validated_data before creating the User instance.
        validated_data['password_hash'] = generate_password_hash(password)
        
        # 3. Instantiate the User model. Now password_hash is guaranteed to be present.
        user = User(**validated_data)
        
        # No need to call user.set_password here for hashing, as it's already done.
        # If set_password has other important side effects besides hashing, you might
        # call it, but ensure it doesn't try to re-hash. For this model,
        # it mostly generates the hash, so this direct approach is better.

        user.save() # This will now succeed as password_hash is not None
        return user

class FeedbackSerializer(DocumentSerializer):
    class Meta:
        model = Feedback
        fields = ['id',  'type', 'title', 'description', 'status']
        read_only_fields = ['created_at', 'resolved_at']


       