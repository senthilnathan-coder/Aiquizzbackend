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
            
            username=data.get('username')
            email=data.get('email')
            password=data.get('password')
            
            if not all([username,email,password]):
                return Response({'error':'All field is required',},status=status.HTTP_400_BAD_REQUEST)
            
            if Admin.objects(email=email).first():
                return Response({'error':'Email already exits'},status=status.HTTP_400_BAD_REQUEST)
            
            admin=Admin(
                username=username,
                email=email
            )
            admin.set_password(password)
            admin.save
            
            return Response({'message':'Admin register succussfully','admin':{'username':admin.username,'email':admin.email}},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)