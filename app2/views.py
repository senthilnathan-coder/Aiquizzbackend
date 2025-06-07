from django.shortcuts import render
from rest_framework.views import APIView
from app2.serializers import *
from app2.models import *
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from mongoengine.errors import DoesNotExist, ValidationError

# Create your views here.
class UserSignupView(APIView):
    def post(self, request):
        try:
            data = request.data
            serializer = UserSerializer(data=data)
            
            if serializer.is_valid():
                user = User(
                    full_name=data['full_name'],
                    phone_number=data['phone_number'],
                    email=data['email'],
                    
                )
                user.set_password(data['password'], data['confirm_password'])
                user.save()
                
                # otp=user.generate_otp()
                # send_mail(
                #     subject='your OTP for email verification',
                #     message=f'your OTP is:{otp}',
                #     from_email=settings.DEFAULT_FROM_EMAIL,
                #     recipient_list=[user.email],
                #     fail_silently=False
                # )
                
                return Response({
                    'message': 'User Register successfully.',
                    'user_id': str(user.id),
                }, status=status.HTTP_201_CREATED)
                
            formatted_errors = {field: errors[0] if isinstance(errors, list) else errors
                                for field, errors in serializer.errors.items()}
            
            return Response(
                {'message': formatted_errors},
                status=status.HTTP_400_BAD_REQUEST
            )
            
            
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# class VerifyEmailOTPView(APIView):
#     def post(self, request):
#         try:
#             email = request.data.get('email')
#             otp = request.data.get('otp')
#             user = User.objects.get(email=email)

#             if user.verify_otp(otp):
#                 user.is_verified = True
#                 user.reset_otp = None
#                 user.otp_expiry = None
#                 user.save()
#                 return Response({'message': 'Email verified successfully'}, status=status.HTTP_200_OK)
#             return Response({'error': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)

#         except User.DoesNotExist:
#             return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class UserLoginView(APIView):
    
    def post(self, request):
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            user = User.objects.get(email=email)
            
            # if not user.is_verified:
            #     return Response(
            #         {'error': 'Email not verified. Please check your email for OTP.'},
            #         status=status.HTTP_403_FORBIDDEN
            #     )
                
            if not user.check_password(password):
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

            user.last_login = datetime.utcnow()
            user.save()

            # Remove old tokens
            UserToken.objects(user=user).delete()
            # Generate new token
            token = UserToken.generate_token(user)

            return Response({
                'message': 'Login successful',
                'user_id': str(user.id),
                'token': token.token
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserLogoutView(APIView):
    def post(self, request):
        token_str = request.data.get('token')
        if not token_str:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = UserToken.objects.get(token=token_str)
            token.delete()
            return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
        except UserToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

class FeedbackView(APIView):
    def post(self, request, pk):
        try:
            user=User.objects.get(pk=pk)
                       
            serializer=FeedbackSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=user)
                return Response({
                'message': 'Feedback submitted successfully'
            }, status=status.HTTP_201_CREATED)
                
            formatted_errors = {field: errors[0] if isinstance(errors, list) else errors
                                for field, errors in serializer.errors.items()}
            
            return Response(
                {'message': formatted_errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ForgotPasswordView(APIView):
    def post(self,request):
        email=request.data.get('email')
        if not email:
            return Response({'error':'email is required'},status=status.HTTP_400_BAD_REQUEST)
        try:
            user=User.objects.get(email=email)
            otp=user.generate_otp()
            
            send_mail(
                subject="Your OTP for Password Reset",
                message=f"Your OTP is: {otp}. It expires in 10 minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False
            )
            return Response({'message':'OTP sent to email'},status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'message':'user not found'},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e :
            return Response({'message':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class ResetPasswordView(APIView):
    def post(self,request):
        email=request.data.get('email')
        otp=request.data.get('otp')
        password=request.data.get('password')
        confirm_password=request.data.get('confirm_password')
        if not all([email,otp,password,confirm_password]):
            return Response({'message':'All fields are required'},status=status.HTTP_400_BAD_REQUEST)
        try:
            user=User.objects.get(email=email)
            if not user.verify_otp(otp):
                return Response({'message':'invalid OTP'},status=status.HTTP_400_BAD_REQUEST)
            user.set_password(password,confirm_password)
            user.reset_otp=None
            user.otp_expiry=None
            user.save()
            return Response({'message':'password reset succussfully'},status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'message':'user not found'},status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserDashboardView(APIView): 
    def post(self, request):
        token_key = request.data.get('token')
        user_id = request.data.get('user_id')  # Get user ID from request

        if not token_key or not user_id:
            return Response({'error': 'Token and user_id are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = UserToken.objects.get(token=token_key)
            if token.expires_at < datetime.utcnow():
                return Response({'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)
            
            user = token.user
            if str(user.id) != str(user_id):
                return Response({'error': 'Token does not match user_id'}, status=status.HTTP_403_FORBIDDEN)

            attempts = QuizAttempt.objects(user=user).order_by('-created_at')
            saved_quizzes = Quiz.objects(user=user).order_by('-created_at')

            # Leaderboard
            user_scores = {}
            for attempt in QuizAttempt.objects():
                uid = str(attempt.user.id)
                user_scores[uid] = user_scores.get(uid, 0) + attempt.score

            sorted_leaderboard = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
            leaderboard = [{'user_id': uid, 'total_score': score, 'rank': i+1} for i, (uid, score) in enumerate(sorted_leaderboard)]
            user_rank = next((entry['rank'] for entry in leaderboard if entry['user_id'] == str(user.id)), None)

            # Quiz streak
            streak = 0
            today = datetime.utcnow().date()
            days_played = sorted(set([a.created_at.date() for a in attempts]), reverse=True)
            for i, day in enumerate(days_played):
                if (today - timedelta(days=i)) == day:
                    streak += 1
                else:
                    break

            # Weak topics
            topic_errors = {}
            for attempt in attempts:
                total = attempt.number_question
                correct = attempt.score
                incorrect = total - correct
                for topic in attempt.topics:
                    topic_errors[topic] = topic_errors.get(topic, 0) + incorrect
            weak_topics = sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]

            # Performance graph
            performance_graph = {}
            for attempt in attempts:
                date_key = attempt.created_at.strftime('%Y-%m-%d')
                performance_graph[date_key] = performance_graph.get(date_key, 0) + attempt.score

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
                'feedback_history': feedback_history
            }, status=status.HTTP_200_OK)

        except UserToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
