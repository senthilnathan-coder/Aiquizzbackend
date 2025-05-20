from django.db import models

# Create your models here.
from mongoengine import *
from datetime import datetime
import bcrypt
from email_validator import validate_email, EmailNotValidError

class Admin(Document):
    fullname = StringField(required=True)
    email = EmailField(required=True)
    password_hash = StringField(required=True)  # Changed from password to password_hash
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'admin',
        'indexes': ['fullname', 'email']
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
        
   