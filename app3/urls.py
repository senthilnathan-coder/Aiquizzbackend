from django.urls import path 

from app3.views import *

urlpatterns=[
    path('admin/signup/',AdminsignupView.as_view(),name='admin_signup'),
    path('admin/signin/',AdminsigninView.as_view(),name='admin_signin'),
    path('admin/logout/',AdminLogoutView.as_view(),name='admin_logout'),
    path('admin/admindashboard/',AdminDashboardView.as_view(),name='admin_dashboard'),
    path('admin/forgotpassword/',AdminForgotPasswordView.as_view(),name='forgotpassword'),
    path('admin/resetpassword/',AdminResetPasswordView.as_view(),name='resetpassword'),
    
]