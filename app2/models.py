from django.db import models

# Create your models here.
from mongoengine import *
from datetime import datetime
import bcrypt

class Admin(Document):
    username=StringField(required=True)
    email=StringField(required=True)
    password=StringField(required=True)
    is_active=BooleanField(default=True)
    created_at=DateTimeField(default=datetime.utcnow)
    last_login=DateTimeField(default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        