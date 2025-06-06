from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from app.models import *
from app3.models import *
from mongoengine import DoesNotExist,ValidationError
from app3.serializers import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from .models import Admin, AdminToken  # Import your models
from .serializers import AdminSerializer  # Your serializer
import uuid
from django.core.mail import send_mail
from django.conf import settings
from app2.models import *

class AdminsignupView(APIView):
    def post(self, request):
        try:
            data = request.data
            serializer = AdminSerializer(data=data)
            
            if serializer.is_valid():
                admin = Admin(
                    email=data['email'],    
                )
                admin.set_password(data['password'])
                admin.save()
                # otp=admin.generate_otp()
                # send_mail(
                #     subject='your otp for email verification',
                #     message=f'your OTP is:{otp}',
                #     from_email=settings.DEFAULT_FROM_EMAIL,
                #     recipient_list=[admin.email],
                #     fail_silently=False
                # )
                
                return Response({
                    'message': 'Admin signup successfully',
                    'admin_id': str(admin.id),
                }, status=status.HTTP_201_CREATED)

            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# class VerifyEmailOTPView(APIView):
#     def post(self, request):
#         try:
#             email = request.data.get('email')
#             otp = request.data.get('otp')
#             admin = Admin.objects.get(email=email)

#             if admin.verify_otp(otp):
#                 admin.is_verified = True
#                 admin.reset_otp = None
#                 admin.otp_expiry = None
#                 admin.save()
#                 return Response({'message': 'Email verified successfully'}, status=status.HTTP_200_OK)
#             return Response({'error': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)

#         except Admin.DoesNotExist:
#             return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminsigninView(APIView):
    def post(self, request):
        try:
            data = request.data
            email = data.get('email')
            password = data.get('password')
            
            if not all([email, password]):
                return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            admin = Admin.objects(email=email).first()
            
            # if not admin.is_verified:
            #     return Response({'message':'Email not verified'},status=status.HTTP_403_FORBIDDEN)
            
            if not admin or not admin.check_password(password):
                return Response({'error': 'Invalid email or password'}, status=status.HTTP_400_BAD_REQUEST)
            
            admin.last_login = datetime.utcnow()
            admin.save()

            # Remove old token(s) before creating new one
            AdminToken.objects(admin=admin).delete()
            
            token_str = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(days=21)
            admintoken = AdminToken(admintoken=token_str, admin=admin, expires_at=expires_at)
            admintoken.save()

            return Response({
                'message': 'Admin login successfully',
                'admin': admin.email,
                'admintoken': admintoken.admintoken
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class AdminLogoutView(APIView):
    def post(self, request):
        try:
            token_str = request.data.get('admintoken')
            if not token_str:
                return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            admintoken = AdminToken.objects(admintoken=token_str).first()
            if not admintoken:
                return Response({'error': 'Invalid or already expired token'}, status=status.HTTP_401_UNAUTHORIZED)

            admintoken.delete()  # Remove token to logout
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)       
        
class AdminForgotPasswordView(APIView):
    def post(self,request):
        email=request.data.get('email')
        if not email:
            return Response({'message':'email is required'},status=status.HTTP_400_BAD_REQUEST)
        try:
            admin=Admin.objects.get(email=email)
            otp=admin.generate_otp()
            
            send_mail(
                subject="Your OTP for Password Reset",
                message=f"Your OTP is: {otp}. It expires in 10 minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False
            )
            return Response({'message':'OTP sent to email'},status=status.HTTP_200_OK)
        except Admin.DoesNotExist:
            return Response({'message':'Admin not found'},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e :
            return Response({'message':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class AdminResetPasswordView(APIView):
    def post(self,request):
        email=request.data.get('email')
        otp=request.data.get('otp')
        password=request.data.get('password')
        confirm_password=request.data.get('confirm_password')
        if not all([email,otp,password,confirm_password]):
            return Response({'message':'All fields are required'},status=status.HTTP_400_BAD_REQUEST)
        try:
            admin=Admin.objects.get(email=email)
            if not admin.verify_otp(otp):
                return Response({'message':'invalid OTP'},status=status.HTTP_400_BAD_REQUEST)
            admin.set_password(password,confirm_password)
            admin.reset_otp=None
            admin.otp_expiry=None
            admin.save()
            return Response({'message':'password reset succussfully'},status=status.HTTP_200_OK)
        except Admin.DoesNotExist:
            return Response({'message':'Admin not found'},status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class AdminDashboardView(APIView):
    def post(self, request):
        token_key = request.data.get('admintoken')
        if not token_key:
            return Response({'error': 'AdminToken is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Use correct field name admintoken in the query
            token = AdminToken.objects.get(admintoken=token_key)
            
            if token.expires_at < datetime.utcnow():
                return Response({'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)
            
            admin = token.admin
            if not admin.is_active:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)

            # Fetch feedback from users
            feedbacks = Feedback.objects().order_by('-created_at')
            feedback_data = [{
                'user_id': str(f.user.id),
                'user_name': f.user.full_name,
                'type': f.type,
                'title': f.title,
                'description': f.description,
                'status': f.status,
                'created_at': f.created_at.strftime('%Y-%m-%d %H:%M')
            } for f in feedbacks]

            # Performance analytics
            attempts = QuizAttempt.objects()
            total_attempts = attempts.count()
            average_score = round(sum(a.score for a in attempts) / total_attempts, 2) if total_attempts else 0

            attempt_distribution = {}
            for attempt in attempts:
                key = attempt.difficulty or 'unknown'
                attempt_distribution[key] = attempt_distribution.get(key, 0) + 1

            performance = {
                'total_attempts': total_attempts,
                'average_score': average_score,
                'attempt_distribution': attempt_distribution
            }

            # User count & details
            users = User.objects()
            user_data = []
            for user in users:
                user_attempts = QuizAttempt.objects(user=user)
                user_data.append({
                    'user_id': str(user.id),
                    'full_name': user.full_name,
                    'email': user.email,
                    'total_attempts': user_attempts.count(),
                    'total_score': sum(a.score for a in user_attempts)
                })

            return Response({
                'admin_id': str(admin.id),
                'feedbacks': feedback_data,
                'performance_analytics': performance,
                'user_count': users.count(),
                'user_details': user_data
            }, status=status.HTTP_200_OK)

        except AdminToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)