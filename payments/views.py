from django.shortcuts import render
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from payments.models import *
from datetime import datetime,timedelta
import hashlib
import hmac
from django.conf import settings
import razorpay
from app2.models import AuthToken


class CreateSubscriptionPlanView(APIView):
    def post(self, request):
        plans = [
            {
                "name": "TRIAL",
                "price": 0.00,
                "duration_days": 1,
                "features": [
                    "3 AI quiz attempts (on login day only)",
                    "Up to 5 questions per attempt",
                    "Supports Text to Quiz feature only",
                    "Access valid only on the day of login",
                    "Designed to help new users explore basic functionality"
                ]
            },
            {
                "name": "BASIC",
                "price": 499.00,
                "duration_days": 30,
                "features": [
                    "Total of 400 credits",
                    "Each credit allows one AI quiz attempt, with up to 40  0 total attempts included",
                    "Supports all AI quiz features (Text, PDF, Image, Video, Audio, Word)",
                    "Full platform access during the plan period"
                ]
            },
            {
                "name": "STANDARD",
                "price": 1199.00,
                "duration_days": 90,
                "features": [
                    "Total of 1000 credits",
                    "Each credit allows one AI quiz attempt, with up to 1000 total attempts included",
                    "Supports all AI quiz features (Text, PDF, Image, Video, Audio, Word)",
                    "Full platform access throughout the subscription period"
                ]
            },
            {
                "name": "PREMIUM",
                "price": 2199.00,
                "duration_days": 180,
                "features": [
                    "Total of 2000 credits",
                    "Each credit allows one AI quiz attempt, with up to 2000 total attempts included",
                    "Supports all AI quiz features (Text, PDF, Image, Video, Audio, Word)",
                    "Full access to all platform tools for 6 months" 
                ]
            },
            {
                "name": "ELITE",
                "price": 4199.00,
                "duration_days": 365,
                "features": [
                    "Total of 4000 credits",
                    "Each credit allows one AI quiz attempt, with up to 4000 total attempts included",
                    "Supports all AI quiz features (Text, PDF, Image, Video, Audio, Word)",
                    "Full platform access throughout the 1-year subscription period"
                ]
            }
        ]
        created = []
        for plan in plans:
            if not SubscriptionPlan.objects(name=plan['name']).first():
                created_plan = SubscriptionPlan(**plan).save()
                created.append({
                    "id": str(created_plan.id),
                    "name": created_plan.name,
                    "price": float(created_plan.price),
                    "duration_days": created_plan.duration_days,
                    "features": created_plan.features
                })

        return Response({
            "message": "Plans created",
            "plans":created})

class ListSubscriptionPlansView(APIView):
    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        data = [{
            'id': str(plan.id),
            'name': plan.name,
            'price': float(plan.price),
            'duration_days': plan.duration_days,
            'features':plan.features
        } for plan in plans]
        return Response({'message':'plan_detail','plans':data})
class CreateSubscriptionOrderView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        plan_id = request.data.get('plan_id')
        token = request.data.get('token')

        if not user_id or not plan_id or not token:
            return Response({'error': 'user_id, plan_id, and token are required'}, status=400)

        try:
            # ✅ Validate token
            token_obj = AuthToken.objects.get(token=token)
            user = token_obj.user

            # ✅ Double-check that token belongs to correct user
            if str(user.id) != str(user_id):
                return Response({'error': 'Token does not match user'}, status=403)

            # ✅ Get plan
            plan = SubscriptionPlan.objects.get(id=plan_id)

            if user.role != 'user':
                return Response({'status': 0, 'error': 'Access denied: not a user'}, status=403)

            # ✅ If TRIAL plan
            if plan.name.upper() == 'TRIAL':
                existing_trial = UserSubscription.objects(user=user, plan=plan).first()
                if existing_trial:
                    return Response({'error': 'Trial plan already used'}, status=403)

                # Deactivate current
                UserSubscription.objects(user=user, is_active=True).update(set__is_active=False)

                start = datetime.utcnow()
                end = start + timedelta(days=plan.duration_days)
                credits = get_initial_credits(plan.name)

                UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    is_active=True,
                    start_date=start,
                    end_date=end,
                    remaining_credits=credits
                )

                return Response({
                    'message': 'Trial subscription activated',
                    'plan': plan.name,
                    'credits': credits,
                    'valid_till': end.isoformat()
                })

            # ✅ Paid Plan – Create Razorpay Order
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = client.order.create({
                "amount": int(plan.price * 100),  # in paise
                "currency": "INR",
                "payment_capture": 1
            })

            # Deactivate existing subscriptions
            UserSubscription.objects(user=user, is_active=True).update(set__is_active=False)

            subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                razorpay_order_id=razorpay_order['id'],
                is_active=False
            )

            return Response({
                "message": "Order created",
                "order_id": razorpay_order['id'],
                "amount": float(plan.price),
                "key_id": settings.RAZORPAY_KEY_ID,
                "plan_name": plan.name,
                "subscription_id": str(subscription.id)
            })

        except AuthToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=403)
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

        
class VerifySubscriptionPaymentView(APIView):
    def post(self, request):
        order_id = request.data.get('order_id')
        payment_id = request.data.get('payment_id')
        signature = request.data.get('signature')

        if not all([order_id, payment_id, signature]):
            return Response({'error': 'Missing order_id, payment_id, or signature'}, status=400)

        try:
            subscription = UserSubscription.objects.get(razorpay_order_id=order_id)

            key_secret = settings.RAZORPAY_KEY_SECRET.encode()
            msg = f"{order_id}|{payment_id}".encode()
            expected_signature = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()
            
            if not settings.DEBUG:
                if not hmac.compare_digest(expected_signature, signature):
                    return Response({'error': 'Invalid payment signature'}, status=400)

            # if expected_signature != signature:
            #     return Response({'error': 'Invalid payment signature'}, status=400)

            # Deactivate any existing subscriptions for the user
            UserSubscription.objects(user=subscription.user, is_active=True).update(set__is_active=False)

            # Set subscription metadata
            subscription.razorpay_payment_id = payment_id
            subscription.razorpay_signature = signature
            subscription.start_date = datetime.utcnow()
            subscription.end_date = subscription.start_date + timedelta(days=subscription.plan.duration_days)
            subscription.remaining_credits = get_initial_credits(subscription.plan.name)
            subscription.is_active = True
            subscription.save()

            return Response({
                'message': 'Subscription activated successfully',
                'user_id': str(subscription.user.id),
                'plan': subscription.plan.name,
                'credits': subscription.remaining_credits,
                'valid_till': subscription.end_date.isoformat()
            })

        except UserSubscription.DoesNotExist:
            return Response({'error': 'Subscription not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)