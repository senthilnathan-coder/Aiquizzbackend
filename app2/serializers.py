from rest_framework_mongoengine.serializers import DocumentSerializer
from app.serializers import *
from app2.models import *
from app.models import *
from rest_framework import serializers
from email_validator import validate_email as email_validator_func, EmailNotValidError

# class UserSerializer(DocumentSerializer):
#     password = serializers.CharField(write_only=True, min_length=8)
#     confirm_password = serializers.CharField(write_only=True)

#     class Meta:
#         model = User
#         fields = ['id', 'full_name', 'phone_number', 'email', 'password', 'confirm_password','reset_otp']
#         read_only_fields = ['id', 'is_active', 'is_verified', 'created_at', 'last_login', 'last_quiz_created_at']

#     def validate(self, data):
#         if data['password'] != data['confirm_password']:
#             raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
#         return data
    
#     def validate_phone_number(self, value):
#         cleaned_phone_number = ''.join(filter(str.isdigit, value))
#         if not (len(cleaned_phone_number) == 10 and cleaned_phone_number.isdigit() and cleaned_phone_number[0] in '6789'):
#             raise serializers.ValidationError("Phone number must be 10 digits and start with 6, 7, 8, or 9.")
#         return cleaned_phone_number

#     def validate_email(self, value):
#         try:
#             email_validator_func(value)
#         except EmailNotValidError:
#             raise serializers.ValidationError("Invalid email address format.")
#         return value

#     def create(self, validated_data):
#         password = validated_data.pop('password')
#         confirm_password = validated_data.pop('confirm_password') 

#         validated_data['password'] = generate_password_hash(password)
#         user = User(**validated_data)
#         user.save() # This will now succeed as password_hash is not None
#         return user

class FeedbackSerializer(DocumentSerializer):
    class Meta:
        model = Feedback
        fields = ['id',  'type', 'title', 'description']
        read_only_fields = ['created_at', 'resolved_at']


       