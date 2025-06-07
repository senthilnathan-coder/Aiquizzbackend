from rest_framework_mongoengine.serializers import DocumentSerializer
from app.serializers import *
from app2.models import *
from app.models import *

class UserSerializer(DocumentSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'phone_number', 'email',  'is_active']
        read_only_fields = ['is_active', 'created_at', 'last_login']

class FeedbackSerializer(DocumentSerializer):
    class Meta:
        model = Feedback
        fields = ['id',  'type', 'title', 'description', 'status']
        read_only_fields = ['created_at', 'resolved_at']


       