from django.db import models
from mongoengine import *
from app2.models import User
from datetime import datetime



class SubscriptionPlan(Document):
    name = StringField(required=True, unique=True)  # e.g. basic, standard
    price = DecimalField(required=True)
    duration_days = IntField(required=True)  # 0 for trial
    created_at = DateTimeField(default=datetime.utcnow)

class UserSubscription(Document):
    user = ReferenceField(User, required=True)
    plan = ReferenceField(SubscriptionPlan, required=True)
    razorpay_order_id = StringField()
    razorpay_payment_id = StringField()
    razorpay_signature = StringField()
    is_active = BooleanField(default=True)
    start_date = DateTimeField(default=datetime.utcnow)
    end_date = DateTimeField()
