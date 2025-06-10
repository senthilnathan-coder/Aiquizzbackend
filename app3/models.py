from django.db import models
# Create your models here.
from mongoengine import *
from datetime import datetime,timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError
import random,string

DEFAULT_EMAIL_OTP="123456"
DEFAULT_OTP_EXPIRY_MINUTES=10
class Admin(Document):
    email = EmailField(required=True)
    password_hash = StringField(required=True)  # Changed from password to password_hash
    is_active = BooleanField(default=True)
    reset_otp=StringField()
    otp_expiry=DateTimeField()
    is_verified=BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'admin',
        'indexes': ['email']
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
    def validate_email_address(email):
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False  # Changed from True to False
    # def generate_otp(self):
    #     otp=''.join(random.choices(string.digits,k=6))
    #     self.reset_otp=otp
    #     self.otp_expiry=datetime.utcnow()+timedelta(minutes=10)
    #     self.save()
    #     return otp
    def verify_otp(self,otp):
        return self.reset_otp == otp and datetime.utcnow() <= self.otp_expiry
        
class AdminToken(Document):
    admintoken = StringField(required=True, unique=True)
    admin = ReferenceField('Admin', required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)

    meta = {'collection': 'admin_tokens'} 