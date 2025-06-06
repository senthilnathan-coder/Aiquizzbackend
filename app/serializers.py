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

    def create(self, validated_data):
        # Convert string IDs to actual references
        if isinstance(validated_data.get('user'), str):
            validated_data['user'] = User.objects.get(id=ObjectId(validated_data['user']))
        if isinstance(validated_data.get('quiz'), str):
            validated_data['quiz'] = Quiz.objects.get(id=ObjectId(validated_data['quiz']))
        return super().create(validated_data)
