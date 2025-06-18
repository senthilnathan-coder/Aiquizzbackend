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
import uuid
from django.core.mail import send_mail
from django.conf import settings
from app2.models import *

class AdminDashboardView(APIView):
    def post(self, request):
        token_key = request.data.get('token')
        admin_id = request.data.get('admin_id')

        if not token_key or not admin_id:
            return Response({'status': 0, 'error': 'Token and Admin ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = AuthToken.objects.get(token=token_key)

            # Token expiry check
            if token.expires_at < datetime.utcnow():
                return Response({'status': 0, 'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)

            admin = token.user
            if str(admin.id) != str(admin_id):
                return Response({'status': 0, 'error': 'Token does not match admin ID'}, status=status.HTTP_403_FORBIDDEN)

            if not admin.is_active:
                return Response({'status': 0, 'error': 'Admin is not active'}, status=status.HTTP_403_FORBIDDEN)

            if admin.role != 'admin':
                return Response({'status': 0, 'error': 'Access denied: Not an admin'}, status=status.HTTP_403_FORBIDDEN)

            # === Feedbacks ===
            feedback_data = []
            for f in Feedback.objects.only('user', 'type', 'title', 'description', 'created_at').order_by('-created_at'):
                try:
                    feedback_data.append({
                        'user_id': str(f.user.id),
                        'user_name': getattr(f.user, 'full_name', ''),
                        'type': f.type,
                        'title': f.title,
                        'description': f.description,
                        'created_at': f.created_at.strftime('%Y-%m-%d %H:%M')
                    })
                except Exception:
                    continue

            # === Performance Analytics ===
            attempts = QuizAttempt.objects.only('score', 'difficulty')
            total_attempts = attempts.count()
            scores = [a.score for a in attempts if a.score is not None]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0

            # Distribution by difficulty
            distribution = {}
            for a in attempts:
                difficulty = a.difficulty or 'unknown'
                distribution[difficulty] = distribution.get(difficulty, 0) + 1

            performance = {
                'total_attempts': total_attempts,
                'average_score': avg_score,
                'attempt_distribution': distribution
            }

            # === User Stats ===
            user_data = []
            users = User.objects(role='user').only('id', 'full_name', 'email')
            for u in users:
                try:
                    u_attempts = QuizAttempt.objects(user=u.id).only('score')
                    scores = [a.score for a in u_attempts if a.score is not None]
                    total_score = sum(scores)
                    user_data.append({
                        'user_id': str(u.id),
                        'full_name': u.full_name,
                        'email': u.email,
                        'total_attempts': len(scores),
                        'total_score': total_score
                    })
                except Exception:
                    continue

            return Response({
                'status': 1,
                'admin_id': str(admin.id),
                'feedbacks': feedback_data,
                'performance_analytics': performance,
                'user_count': users.count(),
                'user_details': user_data
            }, status=status.HTTP_200_OK)

        except AuthToken.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)