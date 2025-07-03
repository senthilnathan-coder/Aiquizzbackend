from django.db import models
from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FileField, ReferenceField, ListField, DictField, IntField, FloatField,GenericReferenceField
from werkzeug.security import generate_password_hash, check_password_hash
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from datetime import datetime,timedelta
import random,string
import uuid
import hashlib
import bcrypt

class User(Document):
    full_name = StringField(required=True, min_length=2, max_length=100)
    phone_number = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    auth_provider = StringField(choices=('email', 'google', 'facebook'), default='email')
    
    is_active = BooleanField(default=False)
    role = StringField(choices=('admin', 'user'), default='user')
    is_verified = BooleanField(default=False)
    
    otp = StringField(default=None, null=True)
    otpExpireIn = DateTimeField(default=None, null=True)
    password_reset_expires = DateTimeField(default=None, null=True)
    
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)
    last_quiz_created_at = DateTimeField(default=None, null=True)
     
    country=StringField(default='india')
    state=StringField()
    
    profile = DictField(default=dict)

    meta = {
        'collection': 'users',
        'indexes': ['email', 'phone_number', 'is_verified', 'role'],
        'strict': False
        
    }

    def clean(self):
        self.phone_number = ''.join(filter(str.isdigit, self.phone_number))
        if not (len(self.phone_number) == 10 and self.phone_number[0] in '6789'):
            raise ValueError("Invalid Indian phone number")
    def set_password(self, raw_password):
        hashed = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt())
        self.password = hashed.decode('utf-8')

    def check_password(self, raw_password):
        if not self.password:
            return False
        return bcrypt.checkpw(raw_password.encode('utf-8'), self.password.encode('utf-8'))
    


class AuthToken(Document):
    token = StringField(required=True, unique=True)
    user = ReferenceField(User, required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)

    meta = {'indexes': ['token', 'user']}

    @staticmethod
    def generate_token(user):
        token_str = str(uuid.uuid4())
        token = AuthToken(
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
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'feedback',
        'indexes': ['user', 'type']
    }