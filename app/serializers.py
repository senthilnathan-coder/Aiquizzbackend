from rest_framework_mongoengine.serializers import DocumentSerializer
from .models import  Quiz, QuizAttempt
from mongoengine import *
from app2.models import *
from bson import ObjectId


class QuizSerializer(DocumentSerializer):
    user = StringField(required=True)

    class Meta:
        model = Quiz
        fields = ['id', 'user', 'title', 'questions', 'number_question', 'difficulty', 'question_type', 
                  'created_at', 'content_type', 'topics']
        


class QuizAttemptSerializer(DocumentSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'user', 'quiz', 'questions', 'number_question',
            'user_answers', 'score', 'difficulty', 'question_type', 'topics'
        ]

    
