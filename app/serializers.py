from rest_framework_mongoengine.serializers import DocumentSerializer
from .models import User, Quiz,QuizAttempt

class UserSerializer(DocumentSerializer):
    class Meta:
        model = User
        fields = ['id', 'profile','full_name', 'phone_number', 'country_code', 'email', 'is_active']
        read_only_fields = ['is_active', 'created_at', 'last_login']

class QuizSerializer(DocumentSerializer):
    class Meta:
        model = Quiz
        fields = '__all__'

class QuizAttemptSerializer(DocumentSerializer):
    class Meta:
        model = QuizAttempt
        fields = '__all__'