from django.urls import path

from .views import *

urlpatterns=[
    path('generate_quiz/',generate_multimodal_quiz,name='generate_quiz')
]