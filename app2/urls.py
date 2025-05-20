from django.urls import path 

from app2.views import *

urlpatterns=[
    path('admin/signup/',AdminsignupView.as_view(),name='AdminsignupView'),
    path('admin/signin/',AdminsignView.as_view(),name='AdminsignView')
    
]