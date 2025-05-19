from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FileField,ReferenceField,ListField,DictField,IntField
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

class QuizAttempt(Document):
    user=ReferenceField("User",required=True)
    questions=ListField(DictField(),required=True)
    user_answers = ListField(StringField())
    score=IntField(required=True)
    total=IntField(required=True)
    difficulty=StringField(required=True)
    question_type=StringField(required=True)
    created_at=DateTimeField(default=datetime.utcnow)

    meta={
        'collection':'quiz_attempts',
        'indexes': ['created_at']
    }
