from rest_framework_mongoengine.serializers import DocumentSerializer
from .models import  Quiz, QuizAttempt
from mongoengine import *
from app2.models import *
from bson import ObjectId


class QuizSerializer(DocumentSerializer):
    class Meta:
        model = Quiz
        fields = [
            'id', 'user', 'title', 'questions', 'number_question',
            'difficulty', 'question_type', 'created_at', 'content_type', 'topics'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['user'] = str(instance.user.id) if instance.user else None
        data['questions'] = instance.questions if instance.questions else []
        data['content_type'] = instance.content_type if instance.content_type else []
        data['topics'] = instance.topics if instance.topics else []
        return data


class QuizAttemptSerializer(DocumentSerializer):
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'user', 'quiz', 'questions', 'number_question',
            'user_answers', 'score', 'difficulty', 'question_type', 'topics'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['user'] = str(instance.user.id) if instance.user else None
        data['quiz'] = str(instance.quiz.id) if instance.quiz else None
        data['questions'] = instance.questions if instance.questions else []
        data['user_answers'] = instance.user_answers if instance.user_answers else []
        data['topics'] = instance.topics if instance.topics else []
        return data