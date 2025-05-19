from django.urls import path 

from app2.views import *

urlpatterns=[
    path('admin/signup',AdminsignupView,name='admin_signup')
    
]