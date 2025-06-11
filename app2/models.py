from django.db import models
from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FileField, ReferenceField, ListField, DictField, IntField, FloatField
from werkzeug.security import generate_password_hash, check_password_hash
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from datetime import datetime,timedelta
import random,string
import uuid
import hashlib

DEFAULT_EMAIL_OTP="123456"
DEFAULT_OTP_EXPIRY_MINUTES=10
# Create your models here.
class User(Document):
    full_name = StringField(required=True, min_length=2, max_length=100)
    phone_number = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    is_active = BooleanField(default=True)
    is_verified = BooleanField(default=False)
    reset_otp = StringField()
    otp_expiry = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)
    last_quiz_created_at = DateTimeField(default=datetime(2000, 1, 1))
    # profile =DictField(default=dict)

    meta = {
        'collection': 'users',
        'indexes': ['email', 'phone_number', 'is_verified']
    }

    def clean(self):
        self.phone_number = ''.join(filter(str.isdigit, self.phone_number))
        if not (len(self.phone_number) == 10 and self.phone_number[0] in '6789'):
            raise ValueError("Invalid Indian phone number")
        try:
            validate_email(self.email)
        except EmailNotValidError:
            raise ValueError("Invalid email address")

    def set_password(self, password, confirm_password):
        if password != confirm_password:
            raise ValueError("Passwords do not match")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # def generate_otp(self):
    #     otp = ''.join(random.choices(string.digits, k=6))
    #     self.reset_otp = otp
    #     self.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    #     self.save()
    #     return otp

    def verify_otp(self, otp):
        return self.reset_otp == otp and self.otp_expiry and datetime.utcnow() <= self.otp_expiry
    # def update_user(self,data:dict,profile_image=None):
    #     updatable_fields=['fullname','phone_number','profile']
    #     for fields in updatable_fields:
    #         if fields in data:
    #             setattr(self,fields,data[fields])
    #     if profile_image:
    #         self.profile['image_url']=profile_image
    #     self.save()


class UserToken(Document):
    token = StringField(required=True, unique=True)
    user = ReferenceField(User, required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)

    meta = {'indexes': ['token', 'user']}

    @staticmethod
    def generate_token(user):
        token_str = str(uuid.uuid4())
        token = UserToken(
            token=token_str,
            user=user,
            expires_at=datetime.utcnow() + timedelta(days=21)
        )
        token.save()
        return token


class Feedback(Document):
    user = ReferenceField(User, required=True)
    type = StringField(required=True, choices=['feedback', 'issue', 'suggestion'])
    title = StringField(required=True)
    description = StringField(required=True)
    status = StringField(default='pending', choices=['pending', 'in_progress', 'resolved', 'closed'])
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'feedback',
        'indexes': ['user', 'type', 'status']
    }