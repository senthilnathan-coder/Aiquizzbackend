from rest_framework_mongoengine.serializers import DocumentSerializer
from app.serializers import *
from app2.models import *
from app.models import *
from rest_framework import serializers



class FeedbackSerializer(DocumentSerializer):
    class Meta:
        model = Feedback
        fields = ['id',  'type', 'title', 'description']
        read_only_fields = ['created_at', 'resolved_at']


       