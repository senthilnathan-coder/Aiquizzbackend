from django.urls import path
from payments.views import *

urlpatterns = [
    path('plans/create/', CreateSubscriptionPlanView.as_view(),name='plans_create'),
    path('plans/', ListSubscriptionPlansView.as_view(),name='plans'),
    path('payment/create/', CreateSubscriptionOrderView.as_view(),name='payment_create'),
    path('payment/verify/', VerifySubscriptionPaymentView.as_view(),name='payment_verify'),
]