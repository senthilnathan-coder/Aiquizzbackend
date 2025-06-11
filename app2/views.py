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

# Create your views here.
class UserSignupView(APIView):
    def post(self, request):
        data = request.data
        serializer = UserSerializer(data=data)

        if not serializer.is_valid():
            errors = {k: (v[0] if isinstance(v, list) else v) for k, v in serializer.errors.items()}
            return Response({'status':0,'message': errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = serializer.save()
            user.reset_otp = DEFAULT_EMAIL_OTP
            # user.otp_expiry = datetime.utcnow() + timedelta(minutes=DEFAULT_OTP_EXPIRY_MINUTES)
            user.save()

            return Response({
                'status':1,
                'message': 'User registered successfully. Verification OTP sent to your email.',
                'user_id': str(user.id),
                
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)     
        
class VerifyEmailOTPView(APIView):
     def post(self, request):
        otp = request.data.get('otp')

        if not otp:
            return Response({'status': 0, 'error': 'OTP is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if otp != DEFAULT_EMAIL_OTP:
                return Response({'status': 0, 'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.filter(reset_otp=DEFAULT_EMAIL_OTP, is_verified=False).first()

            if not user:
                return Response({'status': 0, 'error': 'No unverified user found for this OTP.'}, status=status.HTTP_404_NOT_FOUND)

            # ✅ Verify user
            user.is_verified = True
            user.reset_otp = None
            user.otp_expiry = None  # Optional: you can remove this line if not using expiry
            user.save()

            return Response({'status': 1, 'message': 'Email verified successfully.'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'status': 0, 'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserLoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({'status':0,'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)

            # ✅ Check if user is verified
            if not user.is_verified:
                return Response({'status':0,'error': 'Email not verified. Please verify to continue'}, status=status.HTTP_403_FORBIDDEN)

            if not user.check_password(password):
                return Response({'status':0,'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

            user.last_login = datetime.utcnow()
            user.save()
            # Remove old token(s)
            UserToken.objects(user=user).delete()
            # Generate new token
            token = UserToken.generate_token(user)

            return Response({
                'status':1,
                'message': 'Login successful',
                'user_id': str(user.id),
                'token': token.token
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'status':0,'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'success':0,'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserLogoutView(APIView):
    def post(self, request):
        token_str = request.data.get('token')
        if not token_str:
            return Response({'status':0,'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = UserToken.objects.get(token=token_str)
            token.delete()
            return Response({'status':1,'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
        except UserToken.DoesNotExist:
            return Response({'status':0,'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

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

class ForgotPasswordView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'status':0,'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            otp = user.generate_otp()
            send_mail(
                subject="Your OTP for Password Reset",
                message=f"Your OTP is: {otp}. It expires in 10 minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return Response({'status':1,'message': 'OTP sent to email'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'status':0,'message': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'status':0,'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResetPasswordView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        password = request.data.get('password')
        confirm_password = request.data.get('confirm_password')

        if not all([email, otp, password, confirm_password]):
            return Response({'message': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            if not user.verify_otp(otp):
                return Response({'message': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(password, confirm_password)
            user.reset_otp = None
            user.otp_expiry = None
            user.save()
            return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserDashboardView(APIView):
    def get(self,request,pk):
        try:
             user=User.objects.get(pk=pk)
             user_data=[
                 {
                     "full_name":user.full_name,
                     "phone_number":user.phone_number,
                     "email":user.email
                 }
             ]
             if not user:
                 return Response({'user not found'},status=400)
             return Response({'user_data':user_data},status=200)
        except Exception as e:
            return Response({'message':str(e)},status=500)
    def post(self, request):
        token_key = request.data.get('token')
        user_id = request.data.get('user_id')

        if not token_key or not user_id:
            return Response({'status':0,'error': 'Token and user_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = UserToken.objects.get(token=token_key)
            if token.expires_at < datetime.utcnow():
                return Response({'status':0,'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)

            user = token.user
            if str(user.id) != str(user_id):
                return Response({'status':0,'error': 'Token does not match user_id'}, status=status.HTTP_403_FORBIDDEN)

            attempts = QuizAttempt.objects(user=user).order_by('-created_at').only('score', 'number_question', 'topics', 'created_at', 'difficulty', 'question_type')
            saved_quizzes = Quiz.objects(user=user).order_by('-created_at').only('title', 'created_at')

            # Leaderboard calculation (cache to dict)
            user_scores = {}
            for attempt in QuizAttempt.objects.only('user', 'score'):
                uid = str(attempt.user.id)
                user_scores[uid] = user_scores.get(uid, 0) + attempt.score

            sorted_leaderboard = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
            leaderboard = [{'user_id': uid, 'total_score': score, 'rank': i + 1} for i, (uid, score) in enumerate(sorted_leaderboard)]
            user_rank = next((entry['rank'] for entry in leaderboard if entry['user_id'] == str(user.id)), None)

            # Quiz streak calculation
            streak = 0
            today = datetime.utcnow().date()
            days_played = sorted({a.created_at.date() for a in attempts}, reverse=True)
            for i, day in enumerate(days_played):
                if (today - timedelta(days=i)) == day:
                    streak += 1
                else:
                    break

            # Weak topics calculation
            topic_errors = {}
            for attempt in attempts:
                incorrect = attempt.number_question - attempt.score
                for topic in attempt.topics:
                    topic_errors[topic] = topic_errors.get(topic, 0) + incorrect
            weak_topics = sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]

            # Performance graph (date: total score)
            performance_graph = {}
            for attempt in attempts:
                date_key = attempt.created_at.strftime('%Y-%m-%d')
                performance_graph[date_key] = performance_graph.get(date_key, 0) + attempt.score

            # Difficulty and question type stats
            difficulty_stats = {'easy': 0, 'medium': 0, 'hard': 0}
            question_type_stats = {'mcq': 0, 'true_false': 0}
            for attempt in attempts:
                if attempt.difficulty in difficulty_stats:
                    difficulty_stats[attempt.difficulty] += 1
                if attempt.question_type in question_type_stats:
                    question_type_stats[attempt.question_type] += 1

            feedbacks = Feedback.objects(user=user).order_by('-created_at')
            feedback_history = FeedbackSerializer(feedbacks, many=True).data

            return Response({
                'status':1,
                'user_id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'quiz_streak_days': streak,
                'weak_topics': [topic for topic, _ in weak_topics],
                'leaderboard_rank': user_rank,
                'total_attempts': len(attempts),
                'saved_quizzes': QuizSerializer(saved_quizzes, many=True).data,
                'attempt_history': QuizAttemptSerializer(attempts, many=True).data,
                'performance_graph': performance_graph,
                'attempt_stats': {
                    'by_difficulty': difficulty_stats,
                    'by_question_type': question_type_stats
                },
                'feedback_history': feedback_history,
            }, status=status.HTTP_200_OK)

        except UserToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
   
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
  
                
      
        