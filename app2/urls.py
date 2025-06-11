from app2.views import *
from django.urls import path

urlpatterns=[
    path('user/signup/', UserSignupView.as_view(), name='signup'),
    path('user/email_verification/',VerifyEmailOTPView.as_view(),name='email_verification'),
    path('user/signin/', UserLoginView.as_view(), name='signin'),
    path('user/logout/',UserLogoutView.as_view(),name='logout'),
    path('userdashboard/', UserDashboardView.as_view(), name='dashboard'),
    path('user/feedback/<str:pk>/',FeedbackView.as_view(),name='feedback'),
    path('user/forgotpassword/',ForgotPasswordView.as_view(),name='forgotpassword'),
    path('user/resetpassword/',ResetPasswordView.as_view(),name='resetpassword'),
    # path('user/update/<str:pk>/',UserUpdateView.as_view(),name='user_update')
    
]