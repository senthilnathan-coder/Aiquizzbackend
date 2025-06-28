from django.urls import path
from flashcard.views import *

urlpatterns=[
    path('flashcard/<str:pk>/',FlashcardView.as_view(),name='flashcard')
]