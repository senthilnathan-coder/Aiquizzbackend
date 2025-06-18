from rest_framework import serializers
from .models import Quiz, QuizAttempt
from app2.models import User
from bson import ObjectId

class QuizSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    user = serializers.CharField()
    title = serializers.CharField()
    questions = serializers.ListField()
    number_question = serializers.IntegerField()
    difficulty = serializers.CharField()
    question_type = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    content_type = serializers.ListField(child=serializers.CharField(), required=False)
    topics = serializers.ListField(child=serializers.CharField(), required=False)

    def create(self, validated_data):
        validated_data['user'] = User.objects.get(id=ObjectId(validated_data['user']))
        return Quiz(**validated_data).save()

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "user": str(instance.user.id) if instance.user else None,
            "title": instance.title,
            "questions": instance.questions or [],
            "number_question": instance.number_question,
            "difficulty": instance.difficulty,
            "question_type": instance.question_type,
            "created_at": instance.created_at,
            "content_type": instance.content_type or [],
            "topics": instance.topics or [],
        }


class QuizAttemptSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    user = serializers.CharField()
    quiz = serializers.CharField()
    questions = serializers.ListField()
    number_question = serializers.IntegerField()
    user_answers = serializers.ListField(child=serializers.DictField(), required=False)
    score = serializers.FloatField()
    difficulty = serializers.CharField()
    question_type = serializers.CharField()
    topics = serializers.ListField(child=serializers.CharField(), required=False)

    def create(self, validated_data):
        validated_data['user'] = User.objects.get(id=ObjectId(validated_data['user']))
        validated_data['quiz'] = Quiz.objects.get(id=ObjectId(validated_data['quiz']))
        return QuizAttempt(**validated_data).save()

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "user": str(instance.user.id) if instance.user else None,
            "quiz": str(instance.quiz.id) if instance.quiz else None,
            "questions": instance.questions or [],
            "number_question": instance.number_question,
            "user_answers": instance.user_answers or [],
            "score": instance.score,
            "difficulty": instance.difficulty,
            "question_type": instance.question_type,
            "topics": instance.topics or [],
        }