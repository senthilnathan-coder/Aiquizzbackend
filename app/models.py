
from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FileField, ReferenceField, ListField, DictField, IntField, FloatField
from werkzeug.security import generate_password_hash, check_password_hash
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from datetime import datetime

class User(Document):
    profile = FileField()
    full_name = StringField(required=True, min_length=2, max_length=100)
    phone_number = StringField(required=True, unique=True)
    country_code = StringField(required=True)
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'users',
        'indexes': [
            'email',
            'phone_number'
        ]
    }

    def set_password(self, password, confirm_password):
        if password != confirm_password:
            raise ValueError("Passwords do not match")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def validate_phone_number(phone_number, country_code):
        try:
            phone_number = ''.join(filter(str.isdigit, phone_number))
            country_code = ''.join(filter(lambda x: x.isdigit() or x == '+', country_code))
            if not country_code.startswith('+'):
                country_code = '+' + country_code
            full_number = country_code + phone_number
            parsed_number = phonenumbers.parse(full_number)
            return phonenumbers.is_valid_number(parsed_number)
        except phonenumbers.phonenumberutil.NumberParseException:
            return False

    @staticmethod
    def validate_email_address(email):
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False

    def clean(self):
        self.country_code = ''.join(filter(lambda x: x.isdigit() or x == '+', self.country_code))
        if not self.country_code.startswith('+'):
            self.country_code = '+' + self.country_code

        self.phone_number = ''.join(filter(str.isdigit, self.phone_number))

        if not self.validate_phone_number(self.phone_number, self.country_code):
            raise ValueError(f"Invalid phone number for country code {self.country_code}")

        if not self.validate_email_address(self.email):
            raise ValueError("Invalid email address")

        if not self.full_name or len(self.full_name.strip()) < 2:
            raise ValueError("Full name must be at least 2 characters long")

class UserStreak(Document):
    user = ReferenceField('User', required=True)
    current_streak = IntField(default=0)
    longest_streak = IntField(default=0)
    last_quiz_date = DateTimeField()
    streak_history = ListField(DictField())

    meta = {
        'collection': 'user_streaks',
        'indexes': ['user', 'current_streak']
    }

class UserPoints(Document):
    user = ReferenceField('User', required=True)
    total_points = IntField(default=0)
    level = IntField(default=1)
    points_history = ListField(DictField())

    meta = {
        'collection': 'user_points',
        'indexes': ['user', 'total_points']
    }

class SavedQuiz(Document):
    user = ReferenceField('User', required=True)
    quiz_attempt = ReferenceField('QuizAttempt')
    notes = StringField()
    saved_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'saved_quizzes',
        'indexes': ['user', 'saved_at']
    }

class Subscription(Document):
    user = ReferenceField('User', required=True)
    plan_name = StringField(required=True)
    credits = IntField(default=0)
    start_date = DateTimeField(default=datetime.utcnow)
    end_date = DateTimeField(required=True)
    is_active = BooleanField(default=True)

    meta = {
        'collection': 'subscriptions',
        'indexes': ['user', 'end_date']
    }

class Payment(Document):
    user = ReferenceField('User', required=True)
    amount = FloatField(required=True)
    transaction_id = StringField(required=True, unique=True)
    payment_date = DateTimeField(default=datetime.utcnow)
    subscription = ReferenceField('Subscription')
    status = StringField(required=True)
    invoice_url = StringField()

    meta = {
        'collection': 'payments',
        'indexes': ['user', 'payment_date', 'transaction_id']
    }

class Feedback(Document):
    user = ReferenceField('User', required=True)
    type = StringField(required=True)  # 'feedback' or 'issue'
    title = StringField(required=True)
    description = StringField(required=True)
    status = StringField(default='pending')
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'feedback',
        'indexes': ['user', 'type', 'status']
    }

class QuizAttempt(Document):
    user = ReferenceField('User', required=True)
    questions = ListField(DictField(), required=True)
    user_answers = ListField(StringField())
    score = IntField(required=True)
    total = IntField(required=True)
    difficulty = StringField(required=True)
    question_type = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    topics = ListField(StringField())  # Store topics covered in this quiz
    accuracy = FloatField()  # Store accuracy percentage
    points_earned = IntField(default=0)
    review_notes = StringField()
    weak_topics = ListField(StringField())  # Topics where accuracy < 60%
    rank = IntField()  # User's rank at the time of attempt
    percentile = FloatField()  # User's percentile ranking

    meta = {
        'collection': 'quiz_attempts',
        'indexes': [
            'created_at',
            ('user', 'created_at'),
            ('score', '-created_at'),
            'topics'
        ]
    }

    def calculate_stats(self):
        # Calculate accuracy
        self.accuracy = (self.score / self.total * 100) if self.total > 0 else 0
        
        # Calculate points (based on difficulty and accuracy)
        difficulty_multiplier = {'easy': 1, 'medium': 2, 'hard': 3}
        self.points_earned = int(self.accuracy * difficulty_multiplier[self.difficulty])
        
        # Identify weak topics (topics with accuracy < 60%)
        topic_scores = {}
        for q, a in zip(self.questions, self.user_answers):
            topic = q.get('topic', 'general')
            correct = a == q['answer']
            topic_scores.setdefault(topic, {'correct': 0, 'total': 0})
            topic_scores[topic]['total'] += 1
            if correct:
                topic_scores[topic]['correct'] += 1
        
        self.weak_topics = [
            topic for topic, scores in topic_scores.items()
            if (scores['correct'] / scores['total'] * 100) < 60
        ]
        
        # Calculate rank and percentile
        better_scores = QuizAttempt.objects(score__gt=self.score).count()
        total_users = QuizAttempt.objects().distinct('user').count()
        self.rank = better_scores + 1
        self.percentile = ((total_users - self.rank) / total_users * 100) if total_users > 0 else 0

    def save(self, *args, **kwargs):
        self.calculate_stats()
        super(QuizAttempt, self).save(*args, **kwargs)
