from django.urls import path
from .views import *

urlpatterns = [
    path('generate_quiz/', MultimodalQuizView.as_view(), name='quiz'),
    path('user/signup/', SignupView.as_view(), name='signup'),
    path('user/signin/', SigninView.as_view(), name='signin'),
    path('get_datas/<str:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('userdashboard/<str:pk>/',UserDashboardView.as_view(),name='userdashboard')
]