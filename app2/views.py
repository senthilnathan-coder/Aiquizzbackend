from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from app.models import *
from app2.models import *
from mongoengine import DoesNotExist,ValidationError




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


class AdminsignView(APIView):
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

                        