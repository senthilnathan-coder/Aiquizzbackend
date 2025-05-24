from django.urls import path
from .views import *

urlpatterns = [
    path('quiz/<str:pk>/', MultimodalQuizView.as_view(), name='quiz'),
    path('user/signup/', UserSignupView.as_view(), name='signup'),
    path('user/signin/', UserLoginView.as_view(), name='signin'),
    path('userdashboard/<str:pk>/', UserDashboardView.as_view(), name='dashboard'),
    path('get_datas/<str:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('user/feedback/<str:pk>/',FeedbackView.as_view(),name='feedback')
    # path('userdashboard/<str:pk>/',UserDashboardView.as_view(),name='UserDashboard'),
]