from django.urls import path
from .views import *

urlpatterns = [
    path('quiz/<str:pk>/', MultimodalQuizView.as_view(), name='quiz'),
    path('submitquiz/<str:pk>/',SubmitQuizView.as_view(),name='submitquiz')
    # path('userdashboard/<str:pk>/',UserDashboardView.as_view(),name='UserDashboard'),
]