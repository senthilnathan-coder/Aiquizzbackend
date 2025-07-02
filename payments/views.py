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
from decimal import Decimal, ROUND_HALF_UP

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
                    "Each credit allows one AI quiz attempt",
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
                    "Each credit allows one AI quiz attempt",
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
                    "Each credit allows one AI quiz attempt",
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
                    "Each credit allows one AI quiz attempt",
                    "Supports all AI quiz features (Text, PDF, Image, Video, Audio, Word)",
                    "Full platform access throughout the 1-year subscription period"
                ]
            }
        ]

        created = []

        for plan in plans:
            # Avoid duplication
            if not SubscriptionPlan.objects(name=plan['name']).first():
                created_plan = SubscriptionPlan(
                    name=plan['name'],
                    price=Decimal(plan['price']),
                    duration_days=plan['duration_days'],
                    features=plan['features']
                ).save()

                price = Decimal(plan['price'])
                # cgst = (base_price * Decimal('0.09')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                # sgst = (base_price * Decimal('0.09')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                # total_price = base_price + cgst + sgst

                created.append({
                    "id": str(created_plan.id),
                    "name": created_plan.name,
                    "price": float(price),
                    # "cgst": float(cgst),
                    # "sgst": float(sgst),
                    # "total_price": float(total_price),
                    "duration_days": created_plan.duration_days,
                    "features": created_plan.features
                })

        return Response({
            "message": "Plans created",
            "plans": created
        })

class ListSubscriptionPlansView(APIView):
    def post(self, request):
        token_key = request.data.get('token')
        user_id = request.data.get('user_id')
        
        if not token_key or not user_id:
            return Response({'status': 0, 'error': 'Token and user_id are required'}, status=400)

        try:
            token = AuthToken.objects.get(token=token_key)

            if str(token.user.id) != str(user_id):
                return Response({'status': 0, 'error': 'Token does not match user'}, status=403)

            user = token.user
            country = (user.country or '').strip().lower()
            state = (user.state or '').strip().lower()

            plans = SubscriptionPlan.objects.all()
            data = []

            for plan in plans:
                base_price = Decimal(plan.price)
                cgst = sgst = igst = Decimal('0.00')
                total_price = base_price
                tax_details = {
                    'base_price': float(base_price)
                }

                if country == 'india':
                    if state == 'tamil nadu':
                        # CGST + SGST
                        cgst = (base_price * Decimal('0.09')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        sgst = (base_price * Decimal('0.09')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        total_price = base_price + cgst + sgst

                        tax_details['cgst'] = float(cgst)
                        tax_details['sgst'] = float(sgst)
                    else:
                        # IGST
                        igst = (base_price * Decimal('0.18')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        total_price = base_price + igst

                        tax_details['igst'] = float(igst)

                tax_details['total_price'] = float(total_price)

                data.append({
                    'id': str(plan.id),
                    'name': plan.name,
                    'duration_days': plan.duration_days,
                    'features': plan.features,
                    **tax_details  # Merge tax details into response
                })

            return Response({
                'status': 1,
                'user_id': str(user.id),
                'country': country,
                'state': state,
                'plans': data
            })

        except AuthToken.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid token'}, status=401)
        except User.DoesNotExist:
            return Response({'status': 0, 'error': 'User not found'}, status=404)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=500)

class CreateSubscriptionOrderView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        plan_id = request.data.get('plan_id')
        token = request.data.get('token')

        if not user_id or not plan_id or not token:
            return Response({'error': 'user_id, plan_id, and token are required'}, status=400)

        try:
            token_obj = AuthToken.objects.get(token=token)
            user = token_obj.user

            if str(user.id) != str(user_id):
                return Response({'error': 'Token does not match user'}, status=403)

            plan = SubscriptionPlan.objects.get(id=plan_id)

            if user.role != 'user':
                return Response({'status': 0, 'error': 'Access denied: not a user'}, status=403)

            # === TRIAL Plan Handling ===
            if plan.name.upper() == 'TRIAL':
                if UserSubscription.objects(user=user, plan=plan).first():
                    return Response({'error': 'Trial plan already used'}, status=403)

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

            # === GST Calculation ===
            base_price = Decimal(plan.price)
            cgst = sgst = igst = Decimal('0.00')
            country = (user.country or '').strip().lower()
            state = (user.state or '').strip().lower()

            if country == 'india':
                if state == 'tamil nadu':
                    cgst = (base_price * Decimal('0.09')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    sgst = (base_price * Decimal('0.09')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    total_price = base_price + cgst + sgst
                else:
                    igst = (base_price * Decimal('0.18')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    total_price = base_price + igst
            else:
                total_price = base_price

            # === Razorpay Order Creation ===
            amount_in_paise = int(total_price * 100)

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1
            })

            # Save subscription as pending
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
                "amount_breakup": {
                    "base_price": float(base_price),
                    **({"cgst": float(cgst), "sgst": float(sgst)} if cgst else {}),
                    **({"igst": float(igst)} if igst else {}),
                    "total": float(total_price)
                },
                "amount_paise": amount_in_paise,
                "key_id": settings.RAZORPAY_KEY_ID,
                "plan_name": plan.name,
                "subscription_id": str(subscription.id)
            },status=200)

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
            },status=200)

        except UserSubscription.DoesNotExist:
            return Response({'error': 'Subscription not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
class CreditsView(APIView):
    def post(self,request):
        user_id = request.data.get('user_id')
        token = request.data.get('token')

        if not user_id or not token:
            return Response({'status': 0, 'error': 'user_id and token are required'}, status=400)

        try:
            token_obj = AuthToken.objects.get(token=token)
            if str(token_obj.user.id) != str(user_id):
                return Response({'status': 0, 'error': 'Token does not match user_id'}, status=403)

            user = token_obj.user

            # Get the latest active subscription
            subscription = UserSubscription.objects(user=user, is_active=True).order_by('-start_date').first()

            if not subscription:
                return Response({'status': 0, 'error': 'No active subscription found'}, status=404)

            if subscription.end_date and subscription.end_date < datetime.utcnow():
                subscription.is_active = False
                subscription.save()
                return Response({'status': 0, 'error': 'Subscription has expired'}, status=403)

            return Response({
                'status': 1,
                'user_id': str(user.id),
                'remaining_credits': subscription.remaining_credits,
                'valid_till': subscription.end_date.isoformat() if subscription.end_date else None,
                'plan': subscription.plan.name
            })

        except AuthToken.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid token'}, status=401)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=500)
            
                
 
           
           