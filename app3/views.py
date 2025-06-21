from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from app.models import *
from app3.models import *
from mongoengine import DoesNotExist,ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
# from .models import Admin  # Import your models
# from .serializers import AdminSerializer  # Your serializer
from django.core.mail import send_mail
from django.conf import settings
from app2.models import *
from payments.models import *

class AdminDashboardView(APIView):
    def post(self, request):
        token_key = request.data.get('token')
        admin_id = request.data.get('admin_id')

        if not token_key or not admin_id:
            return Response({'status': 0, 'error': 'Token and Admin ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = AuthToken.objects.get(token=token_key)

            # Token checks
            if token.expires_at < datetime.utcnow():
                return Response({'status': 0, 'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)

            admin = token.user
            if str(admin.id) != str(admin_id):
                return Response({'status': 0, 'error': 'Token does not match admin ID'}, status=status.HTTP_403_FORBIDDEN)

            if not admin.is_active:
                return Response({'status': 0, 'error': 'Admin is not active'}, status=status.HTTP_403_FORBIDDEN)

            if admin.role != 'admin':
                return Response({'status': 0, 'error': 'Access denied: Not an admin'}, status=status.HTTP_403_FORBIDDEN)

            # === Feedbacks === (batch load user IDs)
            feedbacks = Feedback.objects.only('user', 'type', 'title', 'description', 'created_at').order_by('-created_at')
            user_ids = list({str(f.user.id) for f in feedbacks})
            users_map = {str(u.id): u.full_name for u in User.objects(id__in=user_ids).only('id', 'full_name')}

            feedback_data = [{
                'user_id': str(f.user.id),
                'user_name': users_map.get(str(f.user.id), ''),
                'type': f.type,
                'title': f.title,
                'description': f.description,
                'created_at': f.created_at.strftime('%Y-%m-%d %H:%M')
            } for f in feedbacks]

            # === Performance Analytics ===
            attempts = QuizAttempt.objects.only('score', 'difficulty')
            scores = []
            distribution = {}
            for a in attempts:
                if a.score is not None:
                    scores.append(a.score)
                key = a.difficulty or 'unknown'
                distribution[key] = distribution.get(key, 0) + 1

            performance = {
                'total_attempts': attempts.count(),
                'average_score': round(sum(scores) / len(scores), 2) if scores else 0,
                'attempt_distribution': distribution
            }

            # === User Stats ===
            users = User.objects(role='user').only('id', 'full_name', 'email')
            user_ids = [u.id for u in users]
            attempt_map = {}
            for a in QuizAttempt.objects(user__in=user_ids).only('user', 'score'):
                uid = str(a.user.id)
                if uid not in attempt_map:
                    attempt_map[uid] = []
                if a.score is not None:
                    attempt_map[uid].append(a.score)

            user_data = []
            for u in users:
                uid = str(u.id)
                scores = attempt_map.get(uid, [])
                user_data.append({
                    'user_id': uid,
                    'full_name': u.full_name,
                    'email': u.email,
                    'total_attempts': len(scores),
                    'total_score': sum(scores)
                })

            # === Subscriptions ===
            subscriptions = UserSubscription.objects.select_related()
            user_ids = [sub.user.id for sub in subscriptions if sub.user]
            user_map = {str(u.id): u.full_name for u in User.objects(id__in=user_ids).only('id', 'full_name')}

            subscription_data = [{
                'user_id': str(sub.user.id),
                'full_name': user_map.get(str(sub.user.id), ''),
                'plan_name': sub.plan.name if sub.plan else '',
                'remaining_credits': sub.remaining_credits,
                'valid_till': sub.end_date.strftime('%Y-%m-%d') if sub.end_date else '',
                'payment_id': sub.razorpay_order_id or 'N/A'
            } for sub in subscriptions if sub.user]

            return Response({
                'status': 1,
                'admin_id': str(admin.id),
                'feedbacks': feedback_data,
                'performance_analytics': performance,
                'user_count': users.count(),
                'user_details': user_data,
                'subscription_data': subscription_data
            }, status=status.HTTP_200_OK)

        except AuthToken.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
