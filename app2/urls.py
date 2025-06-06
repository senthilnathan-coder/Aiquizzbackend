from app2.views import *
from django.urls import path

urlpatterns=[
    path('user/signup/', UserSignupView.as_view(), name='signup'),
    path('user/signin/', UserLoginView.as_view(), name='signin'),
    path('user/logout/',UserLogoutView.as_view(),name='logout'),
    path('userdashboard/', UserDashboardView.as_view(), name='dashboard'),
    path('user/feedback/<str:pk>/',FeedbackView.as_view(),name='feedback'),
    path('forgotpassword/',ForgotPasswordView.as_view(),name='forgotpassword'),
    path('resetpassword/',ResetPasswordView.as_view(),name='resetpassword')
]