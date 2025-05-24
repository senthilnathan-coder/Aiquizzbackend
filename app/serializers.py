from rest_framework_mongoengine.serializers import DocumentSerializer
from .models import User, Quiz, QuizAttempt, UserStreak, UserPoints, SavedQuiz, Feedback
from mongoengine import *

class UserSerializer(DocumentSerializer):
    class Meta:
        model = User
        fields = ['id', 'profile', 'full_name', 'phone_number', 'country_code', 'email', 'is_active']
        read_only_fields = ['is_active', 'created_at', 'last_login']

class QuizSerializer(DocumentSerializer):
    user = StringField(required=True)  # Add this line to handle user ID as string
    
    class Meta:
        model = Quiz
        fields = ['id', 'user', 'title', 'questions', 'difficulty', 'question_type', 
                 'created_at', 'content_type', 'topics']
        read_only_fields = ['created_at']

class QuizAttemptSerializer(DocumentSerializer):
    user = StringField(required=True)  # Add this line
    quiz = StringField(required=True)  # Add this line
    
    class Meta:
        model = QuizAttempt
        fields = ['id', 'user', 'quiz', 'questions', 'user_answers', 'score', 'total',
                 'difficulty', 'question_type', 'created_at', 'completed_at', 'topics',
                 'accuracy', 'points_earned', 'review_notes', 'weak_topics', 'rank',
                 'percentile', 'time_taken', 'content_types']
        read_only_fields = ['created_at', 'completed_at', 'accuracy', 'points_earned',
                          'rank', 'percentile']

class UserStreakSerializer(DocumentSerializer):
    class Meta:
        model = UserStreak
        fields = ['id', 'user', 'current_streak', 'longest_streak', 'last_quiz_date',
                 'streak_history']
        read_only_fields = ['current_streak', 'longest_streak', 'last_quiz_date',
                          'streak_history']

class UserPointsSerializer(DocumentSerializer):
    class Meta:
        model = UserPoints
        fields = ['id', 'user', 'total_points', 'level', 'points_history']
        read_only_fields = ['total_points', 'level', 'points_history']

class SavedQuizSerializer(DocumentSerializer):
    class Meta:
        model = SavedQuiz
        fields = ['id', 'user', 'quiz_attempt', 'notes', 'saved_at', 'tags']
        read_only_fields = ['saved_at']

class FeedbackSerializer(DocumentSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'user', 'type', 'title', 'description', 'status']
        read_only_fields = ['created_at', 'resolved_at']

class UserDashboardSerializer(DocumentSerializer):
    quiz_attempts = QuizAttemptSerializer(many=True, read_only=True)
    streak = UserStreakSerializer(read_only=True)
    points = UserPointsSerializer(read_only=True)
    saved_quizzes = SavedQuizSerializer(many=True, read_only=True)
    feedback_history = FeedbackSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'full_name', 'quiz_attempts', 'streak', 'points',
                 'saved_quizzes', 'feedback_history']
        read_only_fields = fields