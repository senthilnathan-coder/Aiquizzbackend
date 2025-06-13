from django.urls import path
from payments.views import *

urlpatterns = [
    path('plans/create/', CreateSubscriptionPlanView.as_view()),
    # path('api/plans/', SubscriptionPlanListView.as_view()),
    path('payment/create/', CreateSubscriptionOrderView.as_view()),
    path('payment/verify/', VerifySubscriptionPaymentView.as_view()),
]