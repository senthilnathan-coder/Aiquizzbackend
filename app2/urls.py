from django.urls import path 

from app2.views import *

urlpatterns=[
    path('admin/signup/',AdminsignupView.as_view(),name='AdminsignupView'),
    path('admin/signin/',AdminsignView.as_view(),name='AdminsignView'),
    path('admin/usermanagement/',UserManagementView.as_view(),name='UserManagementView'),
    path('admin/usermanagement/<str:pk>/',UserManagementView.as_view(),name='UserManagementView'),
    path('admin/userfeedback/',FeedbackManagementView.as_view(),name='FeedbackManagementView'),
    path('admin/analytics/',PerformanceAnalyticsView.as_view(),name='PerformanceAnalyticsView')
    
]