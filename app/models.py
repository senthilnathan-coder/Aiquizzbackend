from mongoengine import Document, StringField, DateTimeField, FileField, ReferenceField, ListField, DictField, IntField
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app2.models import *


class Quiz(Document):
    user = ReferenceField(User, required=True, reverse_delete_rule=2)  # CASCADE
    title = StringField(required=True)
    questions = ListField(DictField(), required=True)
    number_question = IntField(required=True)
    difficulty = StringField(required=True, choices=['easy', 'medium', 'hard'])
    question_type = StringField(required=True, choices=['mcq', 'true_false','both'])
    created_at = DateTimeField(default=datetime.utcnow)
    content_type = ListField(StringField(choices=[
        'text', 'image', 'audio', 'video', 'url',
        'word', 'ppt', 'excel', 'pdf'
    ]))
    topics = ListField(StringField())

    meta = {
        'collection': 'quiz',
        'indexes': [
            '-created_at',
            'user',
            'difficulty',
            'question_type',
            'topics'
        ],
        'ordering': ['-created_at'],
        'auto_create_index': True
    }

    def extract_content_topics(self):
        if hasattr(self, 'source_content'):
            content_text = self.source_content.get('text', '')
            for ctype in self.content_type:
                content_text += '\n' + self.source_content.get(ctype, '')

            if content_text:
                self.topics = ['general']  # Placeholder for AI-based topic detection

    def save(self, *args, **kwargs):
        if not self.topics:
            self.extract_content_topics()
        return super(Quiz, self).save(*args, **kwargs)
        

class QuizAttempt(Document):
    user = ReferenceField(User, required=True, reverse_delete_rule=2)
    quiz = ReferenceField(Quiz, required=True, reverse_delete_rule=3)
    questions = ListField(DictField(), required=True)
    number_question = IntField(required=True)
    user_answers = ListField(StringField())
    score = IntField(required=True)
    difficulty = StringField(required=True)
    question_type = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    completed_at = DateTimeField()
    topics = ListField(StringField())

    meta = {
        'collection': 'quiz_attempts',
        'indexes': [
            '-created_at',
            'user',
            'quiz',
            ('user', '-created_at'),
            ('score', '-created_at'),
            'topics'
        ],
        'ordering': ['-created_at'],
        'auto_create_index': True
    }
    
class UserPayment(Document):
    user=ReferenceField(User,required=True)
    amount=IntField()
    is_paid=BooleanField(required=True)
    payment_at=DateTimeField(default=datetime.utcnow())
    
    meta={
        'collection':'payment'
    }
    
    @property
    def quiz_credits(self):
        return self.amount // 50

class PaidQuizUsage(Document):
    user=ReferenceField(User,required=True)
    payment=ReferenceField(UserPayment,required=True)
    used_count=IntField(default=0)
    
    meta = {'collection': 'paid_quiz_usage'}
    