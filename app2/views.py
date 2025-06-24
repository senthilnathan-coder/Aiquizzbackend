from django.shortcuts import render
from rest_framework.views import APIView
from app2.serializers import *
from app2.models import *
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from mongoengine.errors import DoesNotExist, ValidationError
from django.core.files.storage import default_storage
import time
from payments.models import *
from django.core.cache import cache

class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'status': 0, 'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)

            if not user.is_verified:
                return Response({'status': 0, 'error': 'Email not verified. Please verify to continue.'}, status=status.HTTP_403_FORBIDDEN)

            if not user.check_password(password):
                return Response({'status': 0, 'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

            user.last_login = datetime.utcnow()
            user.save()
        
            # Remove old token(s)
            AuthToken.objects(user=user).delete()
            # Generate new token
            token = AuthToken.generate_token(user)


            return Response({
                'status': 1,
                'message': 'Login successful',
                'full_name': user.full_name,
                'user_id': str(user.id),
                'token': token.token,
                'role': user.role
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeedbackView(APIView):
    def post(self, request, pk):
        try:
            user = User.objects.only('id').get(pk=pk)
        except User.DoesNotExist:
            return Response({'status':0,'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response({'status':1,'message': 'Feedback submitted successfully'}, status=status.HTTP_201_CREATED)
        else:
            formatted_errors = {k: (v[0] if isinstance(v, list) else v) for k, v in serializer.errors.items()}
            return Response({'status':0,'message': formatted_errors}, status=status.HTTP_400_BAD_REQUEST)



class UserDashboardView(APIView):
    def post(self, request):
        token_key = request.data.get('token')
        user_id = request.data.get('user_id')

        if not token_key or not user_id:
            return Response({'status': 0, 'error': 'Token and user_id are required'}, status=400)

        try:
            token = AuthToken.objects.only('token', 'user', 'expires_at').get(token=token_key)

            if token.expires_at < datetime.utcnow():
                return Response({'status': 0, 'error': 'Token has expired'}, status=401)

            user = token.user
            if str(user.id) != str(user_id):
                return Response({'status': 0, 'error': 'Token does not match user_id'}, status=403)
            if not user.is_verified:
                return Response({'status': 0, 'error': 'User is not verified'}, status=403)
            if user.role != 'user':
                return Response({'status': 0, 'error': 'Access denied: not a user'}, status=403)

            # Optional caching for speed
            cache_key = f"user_dashboard_{user.id}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response)

            # Subscription
            active_subscription = UserSubscription.objects(user=user, is_active=True).only('plan', 'remaining_credits', 'end_date').first()
            subscription_info = {
                "plan": active_subscription.plan.name if active_subscription and active_subscription.plan else None,
                "credits": active_subscription.remaining_credits if active_subscription else 0,
                "valid_till": active_subscription.end_date.isoformat() if active_subscription and active_subscription.end_date else None
            }

            # Quiz Attempts and Saved Quizzes
            attempts = list(QuizAttempt.objects(user=user.id).only('user','quiz','score', 'topics', 'difficulty', 'question_type', 'created_at', 'number_question','questions','user_answers').order_by('-created_at'))
            saved_quizzes = list(Quiz.objects(user=user.id).only('user','questions','number_question','question_type','title', 'topics', 'difficulty', 'content_type', 'created_at').order_by('-created_at'))

            user_total_score = 0
            played_dates = set()
            topic_errors = {}
            performance_graph = {}
            difficulty_stats = {'easy': 0, 'medium': 0, 'hard': 0}
            question_type_stats = {'mcq': 0, 'true_false': 0}

            today = datetime.utcnow().date()

            for a in attempts:
                score = float(a.score or 0)
                user_total_score += score

                if a.created_at:
                    date_played = a.created_at.date()
                    played_dates.add(date_played)

                    key = a.created_at.strftime('%Y-%m-%d')
                    performance_graph[key] = performance_graph.get(key, 0) + score

                incorrect = (a.number_question or 0) - score
                for topic in a.topics or []:
                    topic_errors[topic] = topic_errors.get(topic, 0) + incorrect

                if a.difficulty in difficulty_stats:
                    difficulty_stats[a.difficulty] += 1
                if a.question_type in question_type_stats:
                    question_type_stats[a.question_type] += 1

            # Streak Calculation
            streak = 0
            for i in range(100):  # Safe upper limit
                if (today - timedelta(days=i)) in played_dates:
                    streak += 1
                else:
                    break

            weak_topics = sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]

            response_data = {
                'status': 1,
                'user_id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'quiz_streak_days': streak,
                'weak_topics': [t for t, _ in weak_topics],
                'total_attempts': len(attempts),
                'total_score': user_total_score,
                'subscription': subscription_info,
                'saved_quizzes': QuizSerializer(saved_quizzes, many=True).data,
                'attempt_history': QuizAttemptSerializer(attempts, many=True).data,
                'performance_graph': performance_graph,
                'attempt_stats': {
                    'by_difficulty': difficulty_stats,
                    'by_question_type': question_type_stats
                }
            }

            # Cache it for 60 seconds
            cache.set(cache_key, response_data, timeout=60)

            return Response(response_data, status=200)

        except AuthToken.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid token'}, status=401)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=500)
class UserUpdateView(APIView):
     def post(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            data = request.data.copy()
            profile_image = request.FILES.get('profile_image')

            image_url = None
            if profile_image:
                filename = f"profile_images/{user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{profile_image.name}"
                path = default_storage.save(filename, profile_image)
                image_url = default_storage.url(path)

            user.update_user(data, profile_image=image_url)

            return Response({
                'message': 'User profile updated successfully',
                'user_id': str(user.id)
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteUserView(APIView):
    def post(self,request,pk):
       try:
            user=User.objects.get(pk=pk)
            if not user:
                return Response({'status':0,'error':'user not found'})
            user.delete()
            return Response({'status':1,'message':'user deleted'})
       except Exception as e:
           return Response({'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        