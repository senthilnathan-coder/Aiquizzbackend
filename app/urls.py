from django.urls import path
from .views import *

urlpatterns = [
    path('quiz/<str:pk>/', MultimodalQuizView.as_view(), name='quiz'),
    path('payment/',MockPaymentView.as_view(),name='mock_payment'),
    path('submitquiz/<str:pk>/',SubmitQuizView.as_view(),name='submitquiz')
    # path('userdashboard/<str:pk>/',UserDashboardView.as_view(),name='UserDashboard'),
]