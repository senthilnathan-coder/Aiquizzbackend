from django.db import models
# Create your models here.
from mongoengine import *
from datetime import datetime,timedelta
import bcrypt
from email_validator import validate_email, EmailNotValidError
import random,string

class Admin(Document):
    email = EmailField(required=True)
    password_hash = StringField(required=True)  # Changed from password to password_hash
    is_active = BooleanField(default=True)
    # role=StringField(required=True)
    reset_otp=StringField()
    otp_expiry=DateTimeField()
    # is_verified=BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'admin',
        'indexes': ['email']
    }
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        
    @staticmethod
    def validate_email_address(email):
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False  # Changed from True to False
    def generate_otp(self):
        otp=''.join(random.choices(string.digits,k=6))
        self.reset_otp=otp
        self.otp_expiry=datetime.utcnow()+timedelta(minutes=10)
        self.save()
        return otp
    def verify_otp(self,otp):
        return self.reset_otp == otp and datetime.utcnow() <= self.otp_expiry
        
class AdminToken(Document):
    admintoken = StringField(required=True, unique=True)
    admin = ReferenceField('Admin', required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)

    meta = {'collection': 'admin_tokens'} 