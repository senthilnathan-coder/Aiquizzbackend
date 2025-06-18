from django.db import models
from mongoengine import *
from app2.models import User
from datetime import datetime

class SubscriptionPlan(Document):
    PLAN_CHOICES = [
        ('TRIAL', 'Trial'),
        ('BASIC', 'Basic'),
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
        ('ELITE', 'Elite')
    ]
    name = StringField(required=True, choices=PLAN_CHOICES, unique=True)
    price = DecimalField(required=True)
    duration_days = IntField(required=True)  # 0 for trial
    created_at = DateTimeField(default=datetime.utcnow)

class UserSubscription(Document):
    user = ReferenceField(User, required=True, unique=True)
    plan = ReferenceField(SubscriptionPlan, required=True)
    razorpay_order_id = StringField()
    razorpay_payment_id = StringField()
    razorpay_signature = StringField()
    is_active = BooleanField(default=True)
    start_date = DateTimeField(default=datetime.utcnow)
    end_date = DateTimeField()
    remaining_credits = IntField(default=0)
    
def  get_initial_credits(plan_name):
         return { 
          'TRIAL': 3,
          'BASIC': 400,
          'STANDARD': 1000,
          'PREMIUM': 2000,
          'ELITE': 4000
        }.get(plan_name.upper(), 0) 