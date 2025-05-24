from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from app.models import *
from app2.models import *
from mongoengine import DoesNotExist,ValidationError

from functools import wraps

def admin_required(func):
    @wraps(func)
    def wrapper(self, request, pk=None, *args, **kwargs):
        try:
            admin = Admin.objects.get(id=pk)
            request.admin = admin
            return func(self, request, pk, *args, **kwargs)
        except Admin.DoesNotExist:
            return Response({'error': 'Unauthorized admin or invalid admin ID'},
                            status=status.HTTP_401_UNAUTHORIZED)
    return wrapper

class AdminsignupView(APIView):
    def post(self,request):
        try:
            data=request.data
            
            fullname=data.get('fullname')
            email=data.get('email')
            password=data.get('password')
            
            if not all([fullname,email,password]):
                return Response({'error':'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

            if not Admin.validate_email_address(email):
                return Response({'error':'invalid email address'},status=status.HTTP_400_BAD_REQUEST)
            
            if Admin.objects(email=email).first():
                return Response({'error':'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
            
            admin=Admin(
                fullname=fullname,
                email=email
            )
            admin.set_password(password)
            admin.save()
            
            return Response({
                'message':'Admin registered successfully',
                'admin':{'fullname':admin.fullname,'email':admin.email}
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminsigninView(APIView):
    def post(self,request):
        try:
            data=request.data
            email=data.get('email')
            password=data.get('password')
            
            if not all([email,password]):
                return Response({'error':'All fields are required'},status=status.HTTP_400_BAD_REQUEST)
            admin=Admin.objects(email=email).first()
            
            # Fix the condition here - it was incorrectly using 'not admin and' instead of 'not admin or'
            if not admin or not admin.check_password(password):
                return Response({'error':'invalid email or password'},status=status.HTTP_400_BAD_REQUEST)
            
            admin.last_login=datetime.utcnow()
            admin.save()
            
            # Don't return the password in the response
            return Response({
                'message':'Admin login successfully',
                'admin':{'email':admin.email}
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)  


class UserManagementView(APIView):
    @admin_required
    def get(self, request,pk):
        try:
            users = User.objects().all()
            user_list = [{
                'id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'phone_number': user.phone_number,
                'country_code': user.country_code,
                'is_active': user.is_active,
                'joined_date': user.created_at.strftime('%Y-%m-%d')
            } for user in users]

            return Response({'users': user_list})

        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @admin_required
    def post(self, request,pk):
        try:
            data = request.data
            user = User(
                full_name=data['full_name'],
                phone_number=data['phone_number'],
                country_code=data['country_code'],
                email=data['email'],
                profile=data['profile']
            )
            user.set_password(data['password'], data['password'])
            user.clean()
            user.save()

            return Response({
                'message': 'User created successfully',
                'user_id': str(user.id)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @admin_required
    def put(self, request,):
        try:
            user = User.objects(id=pk).first()
            if not user:
                return Response({'error': 'User not found'}, 
                              status=status.HTTP_404_NOT_FOUND)

            data = request.data
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'phone_number' in data:
                user.phone_number = data['phone_number']
            if 'country_code' in data:
                user.country_code = data['country_code']
            if 'email' in data:
                user.email = data['email']
            if 'password' in data:
                user.set_password(data['password'], data['password'])
            if 'profile' in data:
                user.profile = data['profile']
            if 'is_active' in data:
                user.is_active = data['is_active']

            user.clean()
            user.save()

            return Response({'message': 'User updated successfully'})

        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @admin_required
    def delete(self, request, pk):
        try:
            user = User.objects(id=pk).first()
            if not user:
                return Response({'error': 'User not found'}, 
                              status=status.HTTP_404_NOT_FOUND)

            user.delete()
            return Response({'message': 'User deleted successfully'})

        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FeedbackManagementView(APIView):
    @admin_required
    def get(self, request,pk):
        try:
            feedbacks = Feedback.objects().all()
            feedback_list = [{
                'id': str(feedback.id),
                'user': {
                    'id': str(feedback.user.id),
                    'full_name': feedback.user.full_name,
                    'email': feedback.user.email
                },
                'type': feedback.type,
                'title': feedback.title,
                'description': feedback.description,
                'status': feedback.status,
                'created_at': feedback.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for feedback in feedbacks]

            return Response({'feedbacks': feedback_list})

        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PerformanceAnalyticsView(APIView):
    @admin_required
    def get(self, request,pk):
        try:
            # Get all quiz attempts
            quiz_attempts = QuizAttempt.objects().all()

            # Overall statistics
            total_attempts = quiz_attempts.count()
            if total_attempts > 0:
                average_score = sum(attempt.score for attempt in quiz_attempts) / total_attempts
                average_accuracy = sum(attempt.accuracy for attempt in quiz_attempts) / total_attempts
            else:
                average_score = 0
                average_accuracy = 0

            # Performance by difficulty level
            difficulty_stats = {
                'easy': {'attempts': 0, 'avg_score': 0, 'avg_accuracy': 0},
                'medium': {'attempts': 0, 'avg_score': 0, 'avg_accuracy': 0},
                'hard': {'attempts': 0, 'avg_score': 0, 'avg_accuracy': 0}
            }

            for attempt in quiz_attempts:
                diff = attempt.difficulty
                difficulty_stats[diff]['attempts'] += 1
                difficulty_stats[diff]['avg_score'] += attempt.score
                difficulty_stats[diff]['avg_accuracy'] += attempt.accuracy

            for diff in difficulty_stats:
                if difficulty_stats[diff]['attempts'] > 0:
                    difficulty_stats[diff]['avg_score'] /= difficulty_stats[diff]['attempts']
                    difficulty_stats[diff]['avg_accuracy'] /= difficulty_stats[diff]['attempts']

            # Get top performing users
            user_performance = {}
            for attempt in quiz_attempts:
                user_id = str(attempt.user.id)
                if user_id not in user_performance:
                    user_performance[user_id] = {
                        'user': {
                            'id': user_id,
                            'full_name': attempt.user.full_name,
                            'email': attempt.user.email
                        },
                        'attempts': 0,
                        'total_score': 0,
                        'avg_accuracy': 0
                    }
                user_performance[user_id]['attempts'] += 1
                user_performance[user_id]['total_score'] += attempt.score
                user_performance[user_id]['avg_accuracy'] += attempt.accuracy

            top_users = sorted(
                [{
                    **perf,
                    'avg_score': perf['total_score'] / perf['attempts'],
                    'avg_accuracy': perf['avg_accuracy'] / perf['attempts']
                } for perf in user_performance.values()],
                key=lambda x: x['avg_score'],
                reverse=True
            )[:10]

            return Response({
                'overall_statistics': {
                    'total_attempts': total_attempts,
                    'average_score': round(average_score, 2),
                    'average_accuracy': round(average_accuracy, 2)
                },
                'difficulty_statistics': difficulty_stats,
                'top_performing_users': top_users
            })

        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)