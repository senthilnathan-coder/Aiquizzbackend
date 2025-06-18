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

            # if not user.check_password(password):
            #     return Response({'status': 0, 'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

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
            token = AuthToken.objects.get(token=token_key)

            if token.expires_at < datetime.utcnow():
                return Response({'status': 0, 'error': 'Token has expired'}, status=401)

            user = token.user
            if str(user.id) != str(user_id):
                return Response({'status': 0, 'error': 'Token does not match user_id'}, status=403)
            if not user.is_verified:
                return Response({'status': 0, 'error': 'User is not verified'}, status=403)
            if user.role != 'user':
                return Response({'status': 0, 'error': 'Access denied: not a user'}, status=403)

            # Load quiz attempts
            attempts = list(
                QuizAttempt.objects(user=user.id).order_by('-created_at').limit(50)
            )

            # Load saved quizzes
            saved_quizzes = list(
                Quiz.objects(user=user.id).order_by('-created_at').limit(10)
            )

            # Rank calculation
            user_total_score = sum(float(a.score or 0) for a in attempts)
            user_scores = []
            all_users = User.objects(role='user', is_verified=True).only('id')

            for u in all_users:
                total = sum(float(a.score or 0) for a in QuizAttempt.objects(user=u.id).only('score'))
                user_scores.append((str(u.id), total))

            user_scores.sort(key=lambda x: x[1], reverse=True)
            user_rank = next((i + 1 for i, (uid, _) in enumerate(user_scores) if uid == str(user.id)), None)

            # Quiz streak calculation
            today = datetime.utcnow().date()
            days_played = sorted({a.created_at.date() for a in attempts if a.created_at}, reverse=True)
            streak = sum(1 for i, day in enumerate(days_played) if (today - timedelta(days=i)) == day)

            # Weak topics
            topic_errors = {}
            for a in attempts:
                incorrect = (a.number_question or 0) - (a.score or 0)
                for topic in a.topics or []:
                    topic_errors[topic] = topic_errors.get(topic, 0) + incorrect
            weak_topics = sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]

            # Performance graph
            performance_graph = {}
            for a in attempts:
                if a.created_at and a.score is not None:
                    date_key = a.created_at.strftime('%Y-%m-%d')
                    performance_graph[date_key] = performance_graph.get(date_key, 0) + float(a.score)

            # Attempt stats
            difficulty_stats = {'easy': 0, 'medium': 0, 'hard': 0}
            question_type_stats = {'mcq': 0, 'true_false': 0}
            for a in attempts:
                if a.difficulty in difficulty_stats:
                    difficulty_stats[a.difficulty] += 1
                if a.question_type in question_type_stats:
                    question_type_stats[a.question_type] += 1

            return Response({
                'status': 1,
                'user_id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'quiz_streak_days': streak,
                'weak_topics': [t for t, _ in weak_topics],
                'leaderboard_rank': user_rank,
                'total_attempts': len(attempts),
                'saved_quizzes': QuizSerializer(saved_quizzes, many=True).data,
                'attempt_history': QuizAttemptSerializer(attempts, many=True).data,
                'performance_graph': performance_graph,
                'attempt_stats': {
                    'by_difficulty': difficulty_stats,
                    'by_question_type': question_type_stats
                },
                'total_score': user_total_score
            }, status=200)

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
        
        