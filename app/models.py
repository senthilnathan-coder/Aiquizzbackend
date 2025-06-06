from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FileField, ReferenceField, ListField, DictField, IntField, FloatField
from werkzeug.security import generate_password_hash, check_password_hash
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from datetime import datetime
from app2.models import *


class Quiz(Document):
    user = ReferenceField(User, required=True)
    title = StringField(required=True)
    questions = ListField(DictField(), required=True)
    number_question = IntField(required=True)
    difficulty = StringField(required=True, choices=['easy', 'medium', 'hard'])
    question_type = StringField(required=True, choices=['mcq', 'true_false'])
    created_at = DateTimeField(default=datetime.utcnow)
    content_type = ListField(StringField(choices=[
        'text', 'image', 'audio', 'video', 'url', 
        'word', 'ppt', 'excel', 'pdf'
    ]))
    topics = ListField(StringField())  
    
    meta = {
        'collection': 'quiz',
        'indexes': [
            'created_at',
            'difficulty',
            'question_type',
            'content_type',
            'topics'
        ]
    }
    
    def extract_content_topics(self):
        # This method will be called to extract topics based on content type
        if not self.source_content:
            return
        # Use AI to analyze content and extract topics
        content_text = self.source_content.get('text', '')
        if self.content_type:
            for ctype in self.content_type:
                if ctype in self.source_content:
                    content_text += '\n' + self.source_content[ctype]
        
        if content_text:
            # Here you would call your AI service to extract topics
            # For now, we'll use placeholder logic
            self.topics = ['general']  # Replace with AI topic extraction
            # self.content_summary = content_text[:500]  # First 500 chars as summary
    
    def save(self, *args, **kwargs):
        if not self.topics:
            self.extract_content_topics()
        super(Quiz, self).save(*args, **kwargs)
        

class QuizAttempt(Document):
    user = ReferenceField(User, required=True)
    quiz = ReferenceField(Quiz, required=True)  # Reference to the original quiz
    questions = ListField(DictField(), required=True)
    number_question=IntField(required=True)
    user_answers = ListField(StringField())
    score = IntField(required=True)
    difficulty = StringField(required=True)
    question_type = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    completed_at = DateTimeField()  # When the quiz was completed
    topics = ListField(StringField())  # Topics covered in this quiz

    meta = {
        'collection': 'quiz_attempts',
        'indexes': [
            'created_at',
            ('user', 'created_at'),
            ('score', '-created_at'),
            'topics',
            'quiz'
        ]
    }
