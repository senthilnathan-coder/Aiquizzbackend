from django.db import models
from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FileField, ReferenceField, ListField, DictField, IntField, FloatField
from werkzeug.security import generate_password_hash, check_password_hash
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from datetime import datetime,timedelta
import random,string
import uuid
import hashlib

# Create your models here.
class User(Document):
    full_name = StringField(required=True, min_length=2, max_length=100)
    phone_number = StringField(required=True, unique=True)
    country_code = StringField(required=True)
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    is_active = BooleanField(default=True)
    reset_otp=StringField()
    otp_expiry=DateTimeField()
    is_verified = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'users',
        'indexes': [
            'email',
            'phone_number'
        ]
    }

    def set_password(self, password, confirm_password):
        if password != confirm_password:
            raise ValueError("Passwords do not match")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def validate_phone_number(phone_number, country_code):
        try:
            phone_number = ''.join(filter(str.isdigit, phone_number))
            country_code = ''.join(filter(lambda x: x.isdigit() or x == '+', country_code))
            if not country_code.startswith('+'):
                country_code = '+' + country_code
            full_number = country_code + phone_number
            parsed_number = phonenumbers.parse(full_number)
            return phonenumbers.is_valid_number(parsed_number)
        except phonenumbers.phonenumberutil.NumberParseException:
            return False

    @staticmethod
    def validate_email_address(email):
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False

    def clean(self):
        self.country_code = ''.join(filter(lambda x: x.isdigit() or x == '+', self.country_code))
        if not self.country_code.startswith('+'):
            self.country_code = '+' + self.country_code

        self.phone_number = ''.join(filter(str.isdigit, self.phone_number))

        if not self.validate_phone_number(self.phone_number, self.country_code):
            raise ValueError(f"Invalid phone number for country code {self.country_code}")

        if not self.validate_email_address(self.email):
            raise ValueError("Invalid email address")

        if not self.full_name or len(self.full_name.strip()) < 2:
            raise ValueError("Full name must be at least 2 characters long")
        
    def generate_otp(self):
        otp=''.join(random.choices(string.digits,k=6))
        self.reset_otp=otp
        self.otp_expiry=datetime.utcnow()+timedelta(minutes=10)
        self.save()
        return otp
    def verify_otp(self,otp):
        return self.reset_otp == otp and datetime.utcnow() <= self.otp_expiry
        
class UserToken(Document):
    token=StringField(required=True,unique=True)
    user=ReferenceField('User',required=True)
    create_at=DateTimeField(default=datetime.utcnow)
    expires_at=DateTimeField(required=True)
    
    def generate_token(user):
        token_str=str(uuid.uuid4())
        expires_at=datetime.utcnow()+timedelta(days=21)
        token=UserToken(token=token_str,user=user,expires_at=expires_at)
        token.save()
        return token
    

class Feedback(Document):
    user = ReferenceField('User', required=True)
    type = StringField(required=True, choices=['feedback', 'issue', 'suggestion'])
    title = StringField(required=True)
    description = StringField(required=True)
    status = StringField(default='pending', choices=['pending', 'in_progress', 'resolved', 'closed'])
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'feedback',
        'indexes': ['user', 'type', 'status', 'created_at']
    }
    
