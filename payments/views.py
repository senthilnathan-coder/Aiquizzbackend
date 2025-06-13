from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from payments.models import *
from datetime import datetime,timedelta
import hashlib
import hmac
from django.conf import settings

class CreateSubscriptionPlanView(APIView):
    def post(self, request):
        plans = [
            {"name": "trial", "price": 0, "duration_days": 0},
            {"name": "basic", "price": 499, "duration_days": 30},
            {"name": "standard", "price": 1199, "duration_days": 90},
            {"name": "premium", "price": 2199, "duration_days": 180},
            {"name": "enterprise", "price": 4199, "duration_days": 365},
        ]
        created = []
        for plan in plans:
            if not SubscriptionPlan.objects(name=plan['name']).first():
                created_plan = SubscriptionPlan(**plan).save()
                created.append({
                    "id": str(created_plan.id),
                    "name": created_plan.name,
                    "price": created_plan.price,
                    "duration_days": created_plan.duration_days
                })
        return Response({"message": "Plans created", "plans": created})
    
class CreateSubscriptionOrderView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        plan_id = request.data.get('plan_id')

        try:
            user = User.objects.get(id=user_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)

            if plan.price == 0:
                return Response({'error': 'No payment needed for trial'}, status=400)

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = client.order.create({
                "amount": plan.price * 100,
                "currency": "INR",
                "payment_capture": 1
            })

            subscription = UserSubscription(
                user=user,
                plan=plan,
                razorpay_order_id=razorpay_order['id'],
                is_active=False  # Will activate after payment verification
            )
            subscription.save()

            return Response({
                "message": "Order created",
                "order_id": razorpay_order['id'],
                "amount": plan.price,
                "key_id": settings.RAZORPAY_KEY_ID,
                "plan_name": plan.name,
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)
        
class VerifySubscriptionPaymentView(APIView):
    def post(self, request):
        order_id = request.data.get('order_id')
        payment_id = request.data.get('payment_id')
        signature = request.data.get('signature')

        try:
            subscription = UserSubscription.objects.get(razorpay_order_id=order_id)

            key_secret = settings.RAZORPAY_KEY_SECRET.encode()
            msg = f"{order_id}|{payment_id}".encode()
            expected_signature = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()

            if expected_signature != signature:
                return Response({'error': 'Invalid payment signature'}, status=400)

            subscription.razorpay_payment_id = payment_id
            subscription.razorpay_signature = signature
            subscription.start_date = datetime.utcnow()
            subscription.end_date = subscription.start_date + timedelta(days=subscription.plan.duration_days)
            subscription.is_active = True
            subscription.save()

            return Response({'message': 'Subscription activated successfully'})

        except UserSubscription.DoesNotExist:
            return Response({'error': 'Subscription not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)