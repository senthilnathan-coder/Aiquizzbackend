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
# from .models import Admin  # Import your models
# from .serializers import AdminSerializer  # Your serializer
import uuid
from django.core.mail import send_mail
from django.conf import settings
from app2.models import *

# class AdminsignupView(APIView):
#     def post(self, request):
#         try:
#             data = request.data
#             serializer = AdminSerializer(data=data)

#             if not serializer.is_valid():
#                 formatted_errors = {
#                     field: errors[0] if isinstance(errors, list) else errors
#                     for field, errors in serializer.errors.items()
#                 }
#                 return Response({'status': 0,'errors': formatted_errors}, status=status.HTTP_400_BAD_REQUEST)

#             email = data['email']
#             if not Admin.validate_email_address(email):
#                 return Response({'status': 0,'error': 'Invalid email format'}, status=status.HTTP_400_BAD_REQUEST)

#             if Admin.objects(email=email).first():
#                 return Response({'status': 0,'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

#             admin = Admin(email=email)
#             admin.set_password(data['password'],data['confirm_password'])
#             admin.reset_otp=DEFAULT_EMAIL_OTP
#             # admin.otp_expiry=datetime.utcnow()+timedelta(DEFAULT_OTP_EXPIRY_MINUTES)
#             admin.save()

#             # Optional: Generate and send OTP
#             # otp = admin.generate_otp()
#             # send_mail(
#             #     subject='Verify your admin email',
#             #     message=f'Your OTP is: {otp}',
#             #     from_email=settings.DEFAULT_FROM_EMAIL,
#             #     recipient_list=[email],
#             #     fail_silently=False
#             # )

#             return Response({
#                 'status': 1,
#                 'message': 'Admin signup successful. Verification OTP sent to email.',
#                 'admin_id': str(admin.id)
#             }, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# class VerifyAdminOTPView(APIView):
#     def post(self, request,pk):
#         otp = request.data.get('otp')

#         if not otp:
#             return Response({'status': 0,'error': 'OTP is required.'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             if otp != DEFAULT_EMAIL_OTP:
#                 return Response({'status': 0, 'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)
#             admin = Admin.objects(pk=pk,reset_otp=DEFAULT_EMAIL_OTP, is_verified=False).first()
#             if not admin:
#                 return Response({'status': 0,'error': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)

#             if admin.verify_otp(otp):
#                 admin.update(
#                     set__is_verified=True,
#                     set__reset_otp=None,
#                     # set__otp_expiry=None
#                 )
#                 return Response({'status': 1,'message': 'Email verified successfully.'}, status=status.HTTP_200_OK)

#             return Response({'status': 0,'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

#         except Exception as e:
#             return Response({'status': 0,'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class AdminsigninView(APIView):
#     def post(self, request):
#         try:
#             data = request.data
#             email = data.get('email')
#             password = data.get('password')

#             if not email or not password:
#                 return Response({'status': 0, 'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

#             admin = Admin.objects(email=email).first()
#             if not admin or not admin.check_password(password):
#                 return Response({'status': 0, 'error': 'Invalid email or password'}, status=status.HTTP_400_BAD_REQUEST)

#             if not admin.is_verified:
#                 return Response({'status': 0, 'error': 'Email not verified. Please verify to continue.'}, status=status.HTTP_401_UNAUTHORIZED)

#             if not admin.is_active:
#                 return Response({'status': 0, 'error': 'Admin is inactive'}, status=status.HTTP_403_FORBIDDEN)

#             admin.update(set__last_login=datetime.utcnow())

#             # ✅ Use AuthToken.generate_token()
#             token_obj = AuthToken.generate_token(admin)

#             return Response({
#                 'status': 1,
#                 'message': 'Admin login successful',
#                 'admin': admin.email,
#                 'admin_id': str(admin.id),
#                 'admintoken': token_obj.token
#             }, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response({'status': 0, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class AdminLogoutView(APIView):
#     def post(self, request):
#         try:
#             token_str = request.data.get('admintoken')
#             if not token_str:
#                 return Response({'status': 0,'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

#             admintoken = AuthToken.objects(admintoken=token_str).first()
#             if not admintoken:
#                 return Response({'status': 0,'error': 'Invalid or expired token'}, status=status.HTTP_401_UNAUTHORIZED)

#             admintoken.delete()  # Remove token to logout
#             return Response({'status': 1,'message': 'Logout successful'}, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class AdminForgotPasswordView(APIView):
#     def post(self, request):
#         email = request.data.get('email')
#         if not email:
#             return Response({'message': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             admin = Admin.objects.get(email=email)
#             otp = admin.generate_otp()

#             send_mail(
#                 subject="Your OTP for Password Reset",
#                 message=f"Your OTP is: {otp}. It expires in 10 minutes.",
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 recipient_list=[email],
#                 fail_silently=False
#             )
#             return Response({'message': 'OTP sent to email'}, status=status.HTTP_200_OK)

#         except DoesNotExist:
#             return Response({'message': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class AdminResetPasswordView(APIView):
#     def post(self, request):
#         email = request.data.get('email')
#         otp = request.data.get('otp')
#         password = request.data.get('password')
#         confirm_password = request.data.get('confirm_password')

#         if not all([email, otp, password, confirm_password]):
#             return Response({'status': 0,'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

#         if password != confirm_password:
#             return Response({'status': 0,'error': 'Passwords do not match'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             admin = Admin.objects.get(email=email)
#             if not admin.verify_otp(otp):
#                 return Response({'message': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)

#             admin.set_password(password)
#             admin.reset_otp = None
#             admin.otp_expiry = None
#             admin.save()

#             return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)

#         except DoesNotExist:
#             return Response({'message': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class AdminDashboardView(APIView):
    def post(self, request):
        token_key = request.data.get('token')
        admin_id = request.data.get('admin_id')

        if not token_key or not admin_id:
            return Response({'status': 0, 'error': 'Token and Admin ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = AuthToken.objects.get(token=token_key)

            # Check token expiry
            if token.expires_at < datetime.utcnow():
                return Response({'status': 0, 'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)

            token = AuthToken.objects.get(token=token_key)
            if token.expires_at < datetime.utcnow():
                return Response({'status': 0, 'error': 'Token has expired'}, status=401)

            user = token.user
            if str(user.id) != str(admin_id):
                return Response({'error': 'Token does not match user_id'}, status=status.HTTP_403_FORBIDDEN)

            if not user.is_active:
                return Response({'status': 0, 'error': 'User is not active'}, status=status.HTTP_403_FORBIDDEN)

            if user.role != 'admin':
                return Response({'status': 0, 'error': 'Only admins can access this dashboard'}, status=status.HTTP_403_FORBIDDEN)

            # === Feedbacks ===
            feedbacks = Feedback.objects.only('user', 'type', 'title', 'description', 'created_at').order_by('-created_at')
            feedback_data = []
            for f in feedbacks:
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

            distribution = {}
            for a in attempts:
                key = a.difficulty or 'unknown'
                distribution[key] = distribution.get(key, 0) + 1

            performance = {
                'total_attempts': total_attempts,
                'average_score': avg_score,
                'attempt_distribution': distribution
            }

            # === User Stats ===
            users = User.objects(role='user').only('full_name', 'email')
            user_data = []
            for u in users:
                try:
                    user_attempts = QuizAttempt.objects(user=u).only('score')
                    total_score = sum(a.score for a in user_attempts if a.score is not None)
                    user_data.append({
                        'user_id': str(u.id),
                        'full_name': u.full_name,
                        'email': u.email,
                        'total_attempts': user_attempts.count(),
                        'total_score': total_score
                    })
                except Exception:
                    continue

            return Response({
                'status': 1,
                'admin_id': str(user.id),
                'feedbacks': feedback_data,
                'performance_analytics': performance,
                'user_count': users.count(),
                'user_details': user_data
            }, status=status.HTTP_200_OK)

        except AuthToken.DoesNotExist:
            return Response({'status': 0, 'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'status': 0, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

